import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime as dt

import pandas as pd
import streamlit as st
from lib.api_client import PantryAPI
from lib.expiry_ui import expiry_card_html
from lib.calorie_ui import render_calorie_tracking
from lib.ui import hero, inject_pastel_theme, notification_panel, sidebar_nav

st.set_page_config(page_title="Dashboard", layout="wide")
inject_pastel_theme()

if not st.session_state.get("token"):
    st.warning("Please sign in from **Home**.")
    st.stop()

api = PantryAPI(token=st.session_state.token)
sidebar_nav("Dashboard")
hero("Dashboard", "Expiry overview, inventory, and calorie tracking at a glance.")

notification_panel(api)


@st.cache_data(ttl=20, show_spinner=False)
def _cached_pantry(token: str):
    return PantryAPI(token=token).pantry_list()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_calories(token: str):
    return PantryAPI(token=token).calories_list()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_me(token: str):
    return PantryAPI(token=token).me()


pantry = _cached_pantry(st.session_state.token)
me = _cached_me(st.session_state.token)
cal_rows = _cached_calories(st.session_state.token)
today = dt.date.today()


def style_row(exp):
    if not exp:
        return "OK", "No date set"
    d = (dt.date.fromisoformat(str(exp)[:10]) - today).days
    if d < 0:
        return "Expired", f"{abs(d)}d ago"
    if d <= 3:
        return "Soon", f"{d}d left"
    if d <= 7:
        return "This week", f"{d}d left"
    return "Fresh", f"{d}d left"


rows = []
for it in pantry:
    icon, hint = style_row(it.get("expiration_date"))
    rows.append({**it, "Status": icon, "Expiry note": hint})

st.subheader("Expiry alerts (color-coded)")
st.caption("Red = expired · orange = use within ~3 days · yellow = this week · green = more time or no date.")
if rows:
    with_exp = [it for it in pantry if it.get("expiration_date")]
    if with_exp:
        cols = st.columns(min(3, len(with_exp)))
        for i, it in enumerate(sorted(with_exp, key=lambda x: str(x.get("expiration_date") or ""))[:9]):
            with cols[i % len(cols)]:
                st.markdown(
                    expiry_card_html(
                        str(it["name"]),
                        float(it.get("quantity") or 0),
                        str(it.get("unit") or ""),
                        it.get("expiration_date"),
                    ),
                    unsafe_allow_html=True,
                )
    else:
        st.info("No expiry dates set — add dates under **Ingredients** for alerts.")

st.subheader("Inventory overview")
if rows:
    df = pd.DataFrame(rows)
    drop = [c for c in ["created_at", "updated_at"] if c in df.columns]
    if drop:
        df = df.drop(columns=drop, errors="ignore")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Your inventory is empty — add items under **Ingredients**.")

st.subheader("Calorie tracking")
render_calorie_tracking(api, me, cal_rows, key_prefix="dash", table_limit=8)
st.page_link("pages/05_Profile_Shop.py", label="Open Profile for targets and full history")
