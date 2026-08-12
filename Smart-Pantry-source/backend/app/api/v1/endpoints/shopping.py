from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import PantryItem, Recipe, ShoppingListItem, User
from app.schemas.shopping import (
    ShoppingFromRecipeIn,
    ShoppingItemCreate,
    ShoppingItemOut,
    ShoppingListOut,
)
from app.services.household_utils import get_household_for_user
from app.services.recipe_catalog import is_app_catalog_cuisine
from app.services.recipe_engine import pantry_normalized_names
from app.services.shopping_service import (
    add_items_from_recipe,
    clear_all_items,
    dedupe_shopping_list,
    get_list,
    get_or_create_list,
    list_items_with_recipe_names,
)

router = APIRouter(prefix="/shopping", tags=["shopping"])


def _hh(db: Session, user: User):
    hh = get_household_for_user(db, user)
    if not hh:
        raise HTTPException(400, "No household — register or join a family plan first.")
    return hh


@router.get("", response_model=ShoppingListOut)
def get_shopping_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    sl = get_list(db, hh.id)
    if not sl:
        return ShoppingListOut(list_id=0, name="Grocery list", items=[])
    dedupe_shopping_list(db, sl)
    items = [ShoppingItemOut(**x) for x in list_items_with_recipe_names(db, sl)]
    return ShoppingListOut(list_id=sl.id, name=sl.name or "Grocery list", items=items)


@router.post("/items", response_model=ShoppingItemOut)
def add_shopping_item(
    body: ShoppingItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hh = _hh(db, user)
    sl = get_or_create_list(db, hh.id)
    name = body.item_name.strip()[:200]
    unit = (body.unit or "each").strip()[:64]
    key = (name.lower(), unit.lower())
    existing = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.shopping_list_id == sl.id)
        .all()
    )
    for row in existing:
        if (row.item_name.strip().lower(), (row.unit or "each").strip().lower()) == key:
            row.quantity = max(0.01, float(body.quantity))
            row.is_checked = False
            db.commit()
            db.refresh(row)
            it = row
            break
    else:
        it = ShoppingListItem(
            shopping_list_id=sl.id,
            item_name=name,
            quantity=body.quantity,
            unit=unit,
        )
        db.add(it)
        db.commit()
        db.refresh(it)
    return ShoppingItemOut(
        id=it.id,
        item_name=it.item_name,
        quantity=it.quantity,
        unit=it.unit,
        is_checked=it.is_checked,
        source_recipe_id=None,
        source_recipe_name=None,
    )


@router.post("/from-recipe")
def add_from_recipe(
    body: ShoppingFromRecipeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add user-selected missing ingredients only (never the full recipe list)."""
    names = [str(n).strip() for n in (body.only_ingredient_names or []) if str(n).strip()]
    if not names:
        raise HTTPException(
            400,
            "Select at least one ingredient to add. Nothing is added automatically.",
        )
    hh = _hh(db, user)
    r = db.get(Recipe, body.recipe_id)
    if not r or not is_app_catalog_cuisine(r.cuisine):
        raise HTTPException(404, "Recipe not found")
    plist = db.query(PantryItem).filter(PantryItem.household_id == hh.id).all()
    pantry_set = pantry_normalized_names(plist)
    sl = get_or_create_list(db, hh.id)
    added = add_items_from_recipe(
        db,
        sl,
        r,
        pantry_set,
        target_servings=body.servings,
        only_ingredient_names=names,
    )
    db.commit()
    return {
        "added": added,
        "recipe_id": r.id,
        "recipe_name": r.name,
        "message": (
            f"Added {added} item(s) to your grocery list."
            if added
            else (
                "No items added."
                if body.only_ingredient_names
                else "Nothing to add — pantry already covers this recipe."
            )
        ),
    }


@router.patch("/items/{item_id}/toggle", response_model=ShoppingItemOut)
def toggle_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    sl = get_or_create_list(db, hh.id)
    it = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.id == item_id, ShoppingListItem.shopping_list_id == sl.id)
        .first()
    )
    if not it:
        raise HTTPException(404, "Item not found")
    it.is_checked = not it.is_checked
    db.commit()
    db.refresh(it)
    rname = None
    if it.source_recipe_id:
        rec = db.get(Recipe, it.source_recipe_id)
        rname = rec.name if rec else None
    return ShoppingItemOut(
        id=it.id,
        item_name=it.item_name,
        quantity=it.quantity,
        unit=it.unit,
        is_checked=it.is_checked,
        source_recipe_id=it.source_recipe_id,
        source_recipe_name=rname,
    )


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    sl = get_or_create_list(db, hh.id)
    it = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.id == item_id, ShoppingListItem.shopping_list_id == sl.id)
        .first()
    )
    if it:
        db.delete(it)
        db.commit()


@router.post("/clear-all")
def clear_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove every item from the household grocery list."""
    hh = _hh(db, user)
    sl = get_list(db, hh.id)
    if not sl:
        return {"removed": 0}
    n = clear_all_items(db, sl)
    return {"removed": n}


@router.post("/clear-checked")
def clear_checked(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hh = _hh(db, user)
    sl = get_or_create_list(db, hh.id)
    n = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.shopping_list_id == sl.id, ShoppingListItem.is_checked.is_(True))
        .delete()
    )
    db.commit()
    return {"removed": n}
