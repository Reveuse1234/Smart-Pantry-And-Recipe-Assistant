import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from lib.api_client import PantryAPI
from lib.ui import hero, inject_pastel_theme, sidebar_nav

st.set_page_config(page_title="Shopping", layout="wide")
inject_pastel_theme()

if not st.session_state.get("token"):
    st.warning("Please sign in from **Home**.")
    st.stop()

api = PantryAPI(token=st.session_state.token)
sidebar_nav("Shopping")

hero(
    "Grocery list",
    "Items appear here only when you add them manually or from a recipe using **Add selected to grocery list**.",
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_shopping(token: str):
    return PantryAPI(token=token).shopping_list()


def _clear_shopping_cache() -> None:
    st.cache_data.clear()


data = _cached_shopping(st.session_state.token)
items = data.get("items") or []

c1, c2 = st.columns([3, 1])
with c1:
    with st.form("add_shop"):
        nm = st.text_input("Add item")
        q1, q2 = st.columns(2)
        with q1:
            qty = st.number_input("Qty", min_value=0.1, value=1.0, step=0.1)
        with q2:
            unit = st.text_input("Unit", value="each")
        if st.form_submit_button("Add to list", use_container_width=True):
            if nm.strip():
                try:
                    api.shopping_add_item(nm.strip(), float(qty), unit.strip() or "each")
                    _clear_shopping_cache()
                    st.success("Added.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.error("Name required.")
with c2:
    if st.button("Clear checked", use_container_width=True):
        try:
            api.shopping_clear_checked()
            _clear_shopping_cache()
            st.rerun()
        except Exception as e:
            st.error(str(e))
    if st.button("Clear entire list", use_container_width=True, type="secondary"):
        try:
            res = api.shopping_clear_all()
            _clear_shopping_cache()
            n = int(res.get("removed") or 0)
            st.success(f"Removed {n} item(s)." if n else "List is already empty.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.subheader(f"{data.get('name', 'Grocery list')}")
if not items:
    st.info(
        "Your list is empty. Add items with the form above, or open **Recipes**, "
        "pick missing ingredients, and tap **Add selected to grocery list**."
    )
else:
    for it in items:
        done = bool(it.get("is_checked"))
        title = f"{'✓ ' if done else ''}**{it.get('item_name')}** — {it.get('quantity')} {it.get('unit')}"
        if it.get("source_recipe_name"):
            title += f" · _for {it['source_recipe_name']}_"
        col_a, col_b, col_c = st.columns([5, 1, 1])
        with col_a:
            st.markdown(title)
        with col_b:
            if st.button("Toggle", key=f"shop_tg_{it['id']}"):
                try:
                    api.shopping_toggle(int(it["id"]))
                    _clear_shopping_cache()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with col_c:
            if st.button("Remove", key=f"shop_rm_{it['id']}"):
                try:
                    api.shopping_delete_item(int(it["id"]))
                    _clear_shopping_cache()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
