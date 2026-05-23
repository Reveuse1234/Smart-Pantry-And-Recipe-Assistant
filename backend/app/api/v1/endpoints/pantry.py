from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import REPO_ROOT
from app.core.database import get_db
from app.models import PantryItem, User
from app.schemas.pantry import PantryItemCreate, PantryItemOut
from app.services.barcode_catalog import lookup_barcode
from app.services.household_utils import get_household_for_user
from app.services.nutrition_pandas import load_nutrition_csv, pantry_nutrition_frame, total_estimated_calories
from app.services.openfoodfacts import fetch_product
from app.services.vision_scan import decode_barcodes, easyocr_read_text, parse_ingredients_from_ocr_lines

router = APIRouter(prefix="/pantry", tags=["pantry"])


def _hh(db: Session, user: User):
    hh = get_household_for_user(db, user)
    if not hh:
        raise HTTPException(400, "No household")
    return hh


@router.get("", response_model=list[PantryItemOut])
def list_pantry(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    items = db.query(PantryItem).filter(PantryItem.household_id == hh.id).order_by(PantryItem.name).all()
    return items


@router.post("", response_model=PantryItemOut)
def add_pantry(
    body: PantryItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hh = _hh(db, user)
    it = PantryItem(
        household_id=hh.id,
        name=body.name.strip(),
        quantity=body.quantity,
        unit=body.unit.strip() or "each",
        category=body.category.strip() or "general",
        expiration_date=body.expiration_date,
        barcode=body.barcode.strip() if body.barcode else None,
        notes=body.notes.strip() if body.notes else None,
        created_by_user_id=user.id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.delete("/{item_id}", status_code=204)
def delete_pantry(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    it = db.query(PantryItem).filter(PantryItem.id == item_id, PantryItem.household_id == hh.id).first()
    if it:
        db.delete(it)
        db.commit()


@router.post("/from-mock-barcode", response_model=PantryItemOut)
def from_mock_barcode(barcode: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    product = lookup_barcode(barcode)
    if not product:
        raise HTTPException(404, "Unknown demo barcode")
    it = PantryItem(
        household_id=hh.id,
        name=str(product["name"]),
        quantity=float(product.get("suggested_qty") or 1),
        unit=str(product.get("default_unit") or "each"),
        category=str(product.get("category") or "general"),
        barcode="".join(c for c in barcode if c.isdigit()) or None,
        created_by_user_id=user.id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.post("/from-openfoodfacts", response_model=PantryItemOut)
def from_openfoodfacts(barcode: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    prod = fetch_product(barcode)
    if not prod:
        raise HTTPException(404, "Product not found in Open Food Facts")
    note = f"Open Food Facts {prod.get('barcode')}"
    if prod.get("calories_per_100g"):
        note += f"; ~{prod['calories_per_100g']} kcal/100g"
    it = PantryItem(
        household_id=hh.id,
        name=str(prod.get("name", "Product"))[:200],
        quantity=1.0,
        unit="each",
        category=str(prod.get("category", "general"))[:80],
        barcode=str(prod.get("barcode")),
        notes=note,
        created_by_user_id=user.id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.get("/nutrition-summary")
def pantry_nutrition_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    items = db.query(PantryItem).filter(PantryItem.household_id == hh.id).all()
    csv_path = REPO_ROOT / "data" / "sample_product_nutrition.csv"
    nut = load_nutrition_csv(csv_path)
    merged = pantry_nutrition_frame(items, nut)
    if merged.empty:
        return {"message": "No pantry items", "total_kcal_estimate": 0, "rows": [], "csv_loaded": not nut.empty}
    rows: list[dict] = []
    for _, row in merged.head(50).iterrows():
        r = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif v == v:
                try:
                    r[k] = float(v) if isinstance(v, (int, float)) else str(v)
                except (TypeError, ValueError):
                    r[k] = str(v)
            else:
                r[k] = None
        rows.append(r)
    return {
        "csv_loaded": not nut.empty,
        "total_kcal_estimate": round(total_estimated_calories(merged), 1),
        "rows": rows,
    }


@router.post("/scan/barcode-image")
async def scan_barcode_image(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    _hh(db, user)
    raw = await file.read()
    found = decode_barcodes(raw)
    return {"barcodes": [{"data": b.data, "type": str(b.type)} for b in found]}


@router.post("/scan/ingredients-ocr")
async def scan_ingredients_ocr(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """OCR a photo of an ingredients list and return parsed pantry-style rows."""
    _hh(db, user)
    raw = await file.read()
    lines = easyocr_read_text(raw)
    ingredients = parse_ingredients_from_ocr_lines(lines)
    note = (
        "Requires EasyOCR + OpenCV on the server. Edit rows before adding; "
        "OCR is approximate for small or glossy text."
    )
    return {"lines": lines, "ingredients": ingredients, "note": note}
