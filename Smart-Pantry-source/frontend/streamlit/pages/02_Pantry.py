import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from lib.api_client import PantryAPI
from lib.expiry_ui import expiry_card_html
from lib.ui import hero, inject_pastel_theme, sidebar_nav

st.set_page_config(page_title="Ingredients", layout="wide")
inject_pastel_theme()

if not st.session_state.get("token"):
    st.warning("Please sign in from **Home**.")
    st.stop()

api = PantryAPI(token=st.session_state.token)
sidebar_nav("Ingredients")
hero(
    "Ingredients",
    "Build your inventory with manual entry or the barcode scanner (camera or photo).",
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_pantry_items(token: str):
    return PantryAPI(token=token).pantry_list()


tab_m, tab_scan, tab_ocr = st.tabs(["Manual", "Scan barcode", "Scan label (OCR)"])

with tab_m:
    with st.form("add"):
        name = st.text_input("Name *")
        qty = st.number_input("Quantity", value=1.0, step=0.1)
        unit = st.text_input("Unit", value="each")
        cat = st.text_input("Category", value="general")
        exp = st.date_input("Expiration", value=None)
        bc = st.text_input("Barcode (optional)")
        notes = st.text_area("Notes")
        if st.form_submit_button("Add to pantry"):
            if name.strip():
                try:
                    api.pantry_add(
                        {
                            "name": name.strip(),
                            "quantity": qty,
                            "unit": unit,
                            "category": cat,
                            "expiration_date": exp.isoformat() if exp else None,
                            "barcode": bc or None,
                            "notes": notes or None,
                        }
                    )
                    st.cache_data.clear()
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.error("Name is required.")


def _scan_image_bytes(cam, upload):
    """Prefer a fresh camera frame when present; otherwise use an uploaded file."""
    if cam is not None:
        return cam.getvalue(), "camera.jpg"
    if upload is not None:
        return upload.getvalue(), upload.name or "upload.jpg"
    return None, ""


with tab_scan:
    st.caption("Use your device camera, or upload a photo if the camera is not available.")

    st.markdown("##### Barcode")
    cam_bc = st.camera_input("Capture barcode", key="cam_bc_pantry")
    up_bc = st.file_uploader("Or upload a barcode photo", type=["jpg", "jpeg", "png", "webp"], key="up_bc_pantry")
    if st.button("Decode barcode", key="decode_bc_btn"):
        raw, fn = _scan_image_bytes(cam_bc, up_bc)
        if not raw:
            st.warning("Take a barcode photo with the camera, or upload an image.")
        else:
            try:
                res = api.pantry_scan_barcode_image(raw, fn)
                codes = res.get("barcodes") or []
                if not codes:
                    st.warning("No barcode found. Try sharper light, hold steady, or type the digits manually.")
                else:
                    st.session_state["_last_barcodes"] = [c["data"] for c in codes]
                    for c in codes:
                        st.write(f"**{c['type']}** · `{c['data']}`")
            except Exception as e:
                st.error(str(e))
    if st.session_state.get("_last_barcodes"):
        pick = st.selectbox("Decoded value", st.session_state["_last_barcodes"], key="pick_bc")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Look up product (Open Food Facts)", key="off_lookup_btn"):
                try:
                    prod = api.pantry_from_off(pick)
                    st.session_state["_off_prefill"] = prod
                    st.success(f"Found: {prod.get('name')}")
                    st.rerun()
                except Exception as e:
                    st.warning(f"Lookup failed: {e}. Add the item manually below.")
        with b2:
            if st.button("Try demo catalog barcode", key="mock_bc_btn"):
                try:
                    prod = api.pantry_from_mock_barcode(pick)
                    st.cache_data.clear()
                    st.success(f"Added {prod.get('name')}")
                    st.rerun()
                except Exception:
                    pass
        pre = st.session_state.get("_off_prefill") or {}
        with st.form("add_from_scan"):
            st.caption("Add to your shared pantry inventory (manual details or from product lookup).")
            qn = st.text_input(
                "Product name *",
                value=str(pre.get("name") or ""),
                key="scan_add_name",
            )
            qqty = st.number_input("Quantity", value=1.0, step=0.1, key="scan_add_qty")
            qunit = st.text_input("Unit", value="each", key="scan_add_unit")
            qcat = st.text_input("Category", value="general", key="scan_add_cat")
            qnotes = st.text_area("Notes (optional)", key="scan_add_notes")
            c1, c2 = st.columns(2)
            with c1:
                submit_scan = st.form_submit_button("Add to pantry", type="primary")
            with c2:
                clear_scan = st.form_submit_button("Clear scan")
            if clear_scan:
                del st.session_state["_last_barcodes"]
                st.rerun()
            if submit_scan:
                if not (qn or "").strip():
                    st.error("Product name is required.")
                else:
                    try:
                        api.pantry_add(
                            {
                                "name": (qn or "").strip(),
                                "quantity": qqty,
                                "unit": qunit,
                                "category": qcat,
                                "expiration_date": None,
                                "barcode": pick,
                                "notes": (qnotes or None) or None,
                            }
                        )
                        st.cache_data.clear()
                        del st.session_state["_last_barcodes"]
                        st.success("Saved.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

with tab_ocr:
    st.caption(
        "Photograph an ingredients list on packaging; the server reads text and suggests rows to add. "
        "Requires EasyOCR on the API host."
    )
    cam_ocr = st.camera_input("Capture ingredients label", key="cam_ocr_pantry")
    up_ocr = st.file_uploader(
        "Or upload a label photo",
        type=["jpg", "jpeg", "png", "webp"],
        key="up_ocr_pantry",
    )
    if st.button("Read label", key="ocr_read_btn"):
        raw, fn = _scan_image_bytes(cam_ocr, up_ocr)
        if not raw:
            st.warning("Capture or upload a photo first.")
        else:
            try:
                res = api.pantry_scan_ingredients_ocr(raw, fn)
                st.session_state["_ocr_ingredients"] = res.get("ingredients") or []
                st.session_state["_ocr_note"] = res.get("note") or ""
                if res.get("lines"):
                    with st.expander("Raw text lines"):
                        for ln in res["lines"][:40]:
                            st.text(ln)
            except Exception as e:
                st.error(str(e))
    ocr_rows = st.session_state.get("_ocr_ingredients") or []
    if ocr_rows:
        st.markdown("##### Suggested items")
        if st.session_state.get("_ocr_note"):
            st.caption(st.session_state["_ocr_note"])
        for i, row in enumerate(ocr_rows):
            if not isinstance(row, dict):
                continue
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.text_input("Name", value=str(row.get("name") or ""), key=f"ocr_nm_{i}")
            with c2:
                st.number_input("Qty", value=float(row.get("quantity") or 1), key=f"ocr_q_{i}", min_value=0.1)
            with c3:
                st.text_input("Unit", value=str(row.get("unit") or "each"), key=f"ocr_u_{i}")
        if st.button("Add all suggested to pantry", type="primary", key="ocr_add_all"):
            added = 0
            for i, row in enumerate(ocr_rows):
                if not isinstance(row, dict):
                    continue
                nm = (st.session_state.get(f"ocr_nm_{i}") or row.get("name") or "").strip()
                if not nm:
                    continue
                try:
                    api.pantry_add(
                        {
                            "name": nm,
                            "quantity": float(st.session_state.get(f"ocr_q_{i}") or row.get("quantity") or 1),
                            "unit": str(st.session_state.get(f"ocr_u_{i}") or row.get("unit") or "each"),
                            "category": str(row.get("category") or "general"),
                        }
                    )
                    added += 1
                except Exception:
                    pass
            if added:
                st.cache_data.clear()
                del st.session_state["_ocr_ingredients"]
                st.success(f"Added {added} item(s).")
                st.rerun()

st.divider()
st.subheader("Your ingredients")
for it in _cached_pantry_items(st.session_state.token):
    c1, c2 = st.columns([6, 1])
    with c1:
        st.markdown(
            expiry_card_html(
                str(it["name"]),
                float(it.get("quantity") or 0),
                str(it.get("unit") or ""),
                it.get("expiration_date"),
            ),
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("Remove", key=f"d{it['id']}"):
            api.pantry_delete(it["id"])
            st.cache_data.clear()
            st.rerun()
