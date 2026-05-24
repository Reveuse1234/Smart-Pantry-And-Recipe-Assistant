import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Optional

import httpx
import pandas as pd
import streamlit as st
from lib.api_client import PantryAPI
from lib.api_errors import api_error_message
from lib.auth_persist import clear_auth_token
from lib.recipe_catalog_constants import APP_CATALOG_CUISINES_ORDERED
from lib.dish_images import render_dish_image_or_unavailable, trusted_dish_image_url
from lib.recipe_steps_ui import render_guide_steps, render_plain_steps, resolve_display_steps
from lib.ui import hero, inject_pastel_theme, notification_panel, sidebar_nav

st.set_page_config(page_title="Recipes", layout="wide")
inject_pastel_theme()
if not st.session_state.get("token"):
    st.warning("Please sign in from **Home**.")
    st.stop()

api = PantryAPI(token=st.session_state.token)
sidebar_nav("Recipes")

_highlight_raw = st.session_state.pop("open_recipe_id", None)
_highlight_rid: Optional[int] = None
_jump_brief: Optional[dict] = None
if _highlight_raw is not None:
    try:
        _highlight_rid = int(_highlight_raw)
    except (TypeError, ValueError):
        _highlight_rid = None

if _highlight_rid is not None:
    try:
        _jump_brief = api.recipe(_highlight_rid)
        cu = str(_jump_brief.get("cuisine") or "").strip()
        if cu in APP_CATALOG_CUISINES_ORDERED:
            st.session_state["recipe_cuisine_choice"] = cu
        st.toast("Opened from Home — your recipe is below.", icon="🍽️")
    except Exception:
        _highlight_rid = None
        _jump_brief = None
        st.warning("That recipe could not be loaded. It may have been removed from the catalog.")

BROWSE_PER_CUISINE = 500


def _load_recipes_for_browse(token: str, cuisine: str, search: str) -> list[dict]:
    try:
        return _cached_recipes(token, cuisine, search)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            clear_auth_token()
            st.warning("Your session expired. Please sign in again from **Home**.")
            st.stop()
        st.error(api_error_message(e))
        st.stop()
    except Exception as e:
        st.error(api_error_message(e))
        st.stop()


def _summary_row_from_detail(d: dict) -> dict:
    """Shape a catalog list row from GET /recipes/{id} detail."""
    return {
        "id": int(d.get("id") or 0),
        "name": str(d.get("name") or ""),
        "cuisine": str(d.get("cuisine") or ""),
        "prep_minutes": int(d.get("prep_minutes") or 0),
        "calories_per_serving": int(d.get("calories_per_serving") or 0),
        "servings": int(d.get("servings") or 4),
    }


def _pin_recipe_on_top(all_rows: list, highlight_id: Optional[int], brief: Optional[dict]) -> list:
    """Put the opened-from-Home recipe first so it stays visible (search slice / first-60 cap)."""
    out = list(all_rows)
    if not highlight_id:
        return out
    pin = int(highlight_id)
    for i, r in enumerate(out):
        if int(r.get("id") or 0) == pin:
            row = out.pop(i)
            return [row] + out
    if brief and int(brief.get("id") or 0) == pin:
        return [_summary_row_from_detail(brief)] + out
    return out


def _render_recipe_expander(
    r: dict, *, key_ns: str, as_expander: bool = True, expanded: bool = False
) -> None:
    """One recipe block: servings, scaled ingredients, steps, pantry match."""
    token = st.session_state.token

    def _body() -> None:
        base_srv = max(1, int(r.get("servings") or 4))
        srv = st.number_input(
            "Servings (people)",
            min_value=1,
            max_value=99,
            value=base_srv,
            key=f"{key_ns}_srv_{r['id']}",
            help="Ingredient amounts scale from the recipe's original yield to this many people.",
        )
        det = _cached_recipe_detail(token, r["id"], int(srv))
        photo_url = trusted_dish_image_url(r.get("image_url")) or trusted_dish_image_url(det.get("image_url"))
        render_dish_image_or_unavailable(
            photo_url,
            dish_name=str(r.get("name") or "Recipe"),
            use_container_width=True,
            caption=str(r.get("name") or ""),
        )

        scaled_rows = det.get("ingredients_scaled") or []

        st.markdown("#### Ingredients for this many people")
        if scaled_rows:
            df = pd.DataFrame(
                [
                    {
                        "Ingredient": x.get("name", ""),
                        "Amount": x.get("amount_display", str(x.get("amount", ""))),
                        "Unit": x.get("unit", ""),
                    }
                    for x in scaled_rows
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("No ingredient list for this recipe.")

        st.caption(
            f"Original recipe yield: {base_srv} people. "
            f"Showing amounts for **{int(srv)}** people"
            + (" (scaled)." if int(srv) != base_srv else ".")
        )
        cals = int(det.get("calories_per_serving") or 0)
        if cals > 0:
            st.caption(
                f"Rough energy guide: about {cals * int(srv)} kcal total for the full dish at this headcount."
            )

        plain_steps, step_src, guide_rows = resolve_display_steps(det)

        st.markdown("#### Method")
        st.caption(
            "Follow each step in order. Use the **scaled ingredient list** above for amounts "
            "unless a step gives a different measure."
        )
        if step_src == "spoonacular" and guide_rows:
            render_guide_steps(guide_rows, key_prefix=f"{key_ns}_{r['id']}")
        elif plain_steps:
            render_plain_steps(plain_steps, key_prefix=f"{key_ns}_{r['id']}")
        else:
            st.warning("No step-by-step instructions stored for this recipe.")

        missing_labels: list[str] = []
        st.markdown("##### Pantry coverage")
        try:
            pm = api.recipe_pantry_match(r["id"])
            ratio = float(pm.get("match_ratio") or 0)
            st.progress(min(1.0, ratio), text=f"Coverage: {ratio:.0%}")
            matched_n = int(pm.get("matched") or 0)
            total_n = int(pm.get("total") or 0)
            missing_raw = pm.get("missing") or []
            for m in missing_raw:
                if isinstance(m, dict):
                    nm = str(m.get("name") or "").strip()
                else:
                    nm = str(m).strip()
                if nm:
                    missing_labels.append(nm)
            if total_n > 0:
                st.success(f"In pantry (or close substitute): **{matched_n}** of **{total_n}** ingredients.")
            if missing_labels:
                st.warning(
                    "Not in pantry (not on your grocery list until you add them): "
                    + ", ".join(missing_labels[:24])
                    + (" ..." if len(missing_labels) > 24 else "")
                )
            hints = pm.get("substitution_hints") or {}
            if hints:
                lines = []
                for ing_name, alts in list(hints.items())[:12]:
                    if not alts:
                        continue
                    lines.append(f"**{ing_name}** — alternatives: {', '.join(alts[:5])}")
                if lines:
                    st.markdown("**Ingredient substitutions**")
                    for ln in lines:
                        st.markdown(f"- {ln}")
        except Exception as e:
            st.caption(f"Coverage unavailable: {e}")

        if missing_labels:
            st.markdown("##### Add to grocery list")
            st.caption("Nothing is added automatically. Choose items, then confirm.")
            picked = st.multiselect(
                "Items to add",
                missing_labels,
                default=[],
                key=f"{key_ns}_shop_pick_{r['id']}",
            )
            if st.button(
                "Add selected to grocery list",
                key=f"{key_ns}_shop_{r['id']}",
                use_container_width=True,
                disabled=not picked,
            ):
                try:
                    res = api.shopping_from_recipe(
                        int(r["id"]),
                        int(srv),
                        only_ingredient_names=picked,
                    )
                    st.success(res.get("message") or "Updated grocery list.")
                    st.page_link("pages/04_Shopping.py", label="Open grocery list →")
                except Exception as e:
                    st.error(str(e))

    if as_expander:
        with st.expander(str(r["name"]), expanded=expanded):
            _body()
    else:
        _body()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_recipes(token: str, cuisine: Optional[str], search: str):
    return PantryAPI(token=token).recipes(cuisine=cuisine, search=search or None)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_recipe_detail(token: str, rid: int, servings: int):
    return PantryAPI(token=token).recipe(rid, servings=servings)


hero("Recipes", "")

notification_panel(api)

q1, q2 = st.columns([2, 1])
with q1:
    search_q = st.text_input("Search by name", placeholder="e.g. curry, pasta, soup", key="recipe_search_q")
with q2:
    choice = st.selectbox(
        "Cuisine",
        list(APP_CATALOG_CUISINES_ORDERED),
        index=None,
        placeholder="Choose a cuisine…",
        help="Opens the right catalog when you tap **View recipe** on Home. Or pick a cuisine to browse.",
        key="recipe_cuisine_choice",
    )

tok = st.session_state.token
sq = search_q.strip()

st.divider()
with st.expander("Ingredient substitution guide", expanded=False):
    st.caption("Common swap groups when you are missing an ingredient (shown per recipe under Pantry coverage).")
    try:
        groups = api.substitution_groups().get("groups") or []
        if not groups:
            st.caption("No substitution groups loaded.")
        for g in groups[:14]:
            st.markdown(f"- {' · '.join(g)}")
    except Exception:
        st.caption("Could not load substitution groups — check that the API is running.")

st.divider()
st.subheader("Recipes")

if choice is None:
    st.info("Select a **cuisine** above to browse recipes.")
else:
    all_rows = list(_load_recipes_for_browse(tok, choice, sq)[:BROWSE_PER_CUISINE])
    if _highlight_rid is not None and sq:
        full_list = list(_load_recipes_for_browse(tok, choice, "")[:BROWSE_PER_CUISINE])
        pin = int(_highlight_rid)
        if any(int(r.get("id") or 0) == pin for r in full_list) and not any(
            int(r.get("id") or 0) == pin for r in all_rows
        ):
            all_rows = full_list
            st.caption("Cleared name search so the recipe you opened from **Home** can appear.")
    all_rows = _pin_recipe_on_top(all_rows, _highlight_rid, _jump_brief)
    rows = all_rows
    if not rows:
        st.info("No recipes match this cuisine and search. Try clearing the search or pick another cuisine.")
    else:
        for r in rows:
            key_ns = choice.replace(" ", "_")
            ex = bool(_highlight_rid is not None and int(r.get("id") or 0) == _highlight_rid)
            _render_recipe_expander(r, key_ns=key_ns, expanded=ex)
