import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from lib.api_client import PantryAPI
from lib.auth_persist import clear_auth_token
from lib.calorie_ui import render_calorie_tracking
from lib.recipe_catalog_constants import APP_CATALOG_CUISINES_ORDERED
from lib.ui import hero, inject_pastel_theme, notification_panel, sidebar_nav

st.set_page_config(page_title="Profile", layout="wide")
inject_pastel_theme()

if not st.session_state.get("token"):
    st.warning("Please sign in from **Home**.")
    st.stop()

api = PantryAPI(token=st.session_state.token)
sidebar_nav("Profile")


@st.cache_data(ttl=30, show_spinner=False)
def _cached_me(token: str):
    return PantryAPI(token=token).me()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_calories(token: str):
    return PantryAPI(token=token).calories_list()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_household(token: str):
    return PantryAPI(token=token).household()


me = _cached_me(st.session_state.token)
cal_rows = _cached_calories(st.session_state.token)
hh = _cached_household(st.session_state.token)
all_cuisines = list(APP_CATALOG_CUISINES_ORDERED)

hero(
    "Profile",
    "Account, family plan, health & diet, cuisines, and calorie tracking.",
)

notification_panel(api)

_, top_r = st.columns([5, 1])
with top_r:
    if st.button("Sign out", use_container_width=True):
        clear_auth_token()
        st.rerun()

tags = [
    "vegetarian",
    "vegan",
    "gluten-free",
    "no-added-sugar",
    "low-sodium",
    "salt-free",
    "dairy-free",
    "nut-free",
    "egg-free",
    "soy-free",
    "shellfish-free",
    "high-protein",
    "low-carb",
    "keto-friendly",
]
health_opts = [
    "diabetes-friendly",
    "heart-healthy",
    "high-fiber",
    "low-carb",
    "celiac",
    "hypertension",
    "nut allergy",
    "dairy allergy",
    "shellfish allergy",
]

with st.form("prof"):
    st.markdown("##### Family plan (shared pantry)")
    hh_name = ""
    if hh:
        hh_name = st.text_input(
            "Household name",
            value=str(hh.get("name") or "My Household"),
            help="Shown to everyone on your shared pantry plan.",
        )
        st.caption(
            f"**Invite code:** `{hh.get('invite_code', '')}` — share when someone signs up "
            "(check **Join a joint family plan** on Home)."
        )
        st.caption("Everyone on the plan sees the same ingredients, expiry alerts, and grocery list.")
    else:
        st.info("No household linked to this account.")

    st.divider()
    st.markdown("##### Health & diet")
    cook_idx = 0 if (me.get("cooking_mode") or "solo") == "solo" else 1
    cook = st.radio(
        "Cooking mode",
        ["Solo", "Family"],
        index=cook_idx,
        horizontal=True,
        help="Family mode is for planning larger portions / household meals. Recommendations still use your pantry.",
    )
    d = st.multiselect("Dietary tags (stricter filters for recipes)", tags, default=me.get("dietary_requirements", []))
    h = st.multiselect("Medical / health records (tags)", health_opts, default=me.get("health_conditions", []))
    ct = st.number_input("Daily calorie target (optional)", value=int(me.get("daily_calorie_target") or 0))
    fav_opts = list(all_cuisines)
    prev_fav = [x for x in (me.get("favorite_cuisines") or []) if x in fav_opts]
    fav = st.multiselect(
        "Favorite cuisines (boosts AI & ranking)",
        fav_opts,
        default=prev_fav,
    )
    notes = st.text_area(
        "Allergies & preferences in your own words (used by AI and tips)",
        value=me.get("ai_preferences") or "",
        height=100,
        help="Mention sugar, salt, specific allergens, or substitutions you need.",
    )
    if st.form_submit_button("Save profile & family plan", use_container_width=True):
        try:
            api.patch_profile(
                d,
                h,
                int(ct) if ct > 0 else None,
                ai_preferences=notes.strip() or None,
                favorite_cuisines=fav,
                cooking_mode="solo" if cook == "Solo" else "family",
            )
            if hh and hh_name.strip() and hh_name.strip() != str(hh.get("name") or ""):
                api.patch_household(hh_name.strip())
            st.cache_data.clear()
            st.success("Profile and family plan saved — recommendations will follow these preferences.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.markdown(f"**Signed in as** `{me.get('email')}` · {me.get('full_name')}")

with st.expander("Change password"):
    with st.form("pwd"):
        cur_pw = st.text_input("Current password", type="password")
        new_pw = st.text_input("New password (min 8 characters)", type="password")
        new_pw2 = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password"):
            if new_pw != new_pw2:
                st.error("New passwords do not match.")
            elif len(new_pw) < 8:
                st.error("New password must be at least 8 characters.")
            else:
                try:
                    api.change_password(cur_pw, new_pw)
                    st.success("Password updated. Use the new password next time you sign in.")
                except Exception as e:
                    st.error(str(e))

st.divider()
st.subheader("Calorie tracking")
render_calorie_tracking(api, me, cal_rows, key_prefix="prof", table_limit=24)
