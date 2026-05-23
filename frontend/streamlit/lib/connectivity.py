"""Detect whether the Smart Pantry API is reachable (Streamlit UI)."""

from __future__ import annotations

import os

import httpx
import streamlit as st

from lib.api_client import DEFAULT_BASE

LAUNCH_HINT = (
    "From the project folder run **`python run_pantryflow.py`** — it starts the API and this web app together."
)


def _health_urls_to_try() -> list[str]:
    """Probe configured API URL first, then common local fallbacks (mis-set BACKEND_URL is common)."""
    seen: set[str] = set()
    out: list[str] = []
    for u in (
        DEFAULT_BASE.rstrip("/"),
        f"http://127.0.0.1:{os.environ.get('API_PORT', '8000').strip() or '8000'}",
        "http://localhost:8000",
    ):
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


@st.cache_data(ttl=8, show_spinner=False)
def _backend_health_probe() -> tuple[bool, str]:
    """Return (ok, detail) where detail names the first working base or explains failure."""
    last_err = "no response"
    for base in _health_urls_to_try():
        try:
            r = httpx.get(f"{base}/health", timeout=2.0)
            if r.status_code == 200:
                return True, base
        except httpx.RequestError as e:
            last_err = str(e)[:120]
        except Exception as e:
            last_err = str(e)[:120]
    return False, last_err


def maybe_show_backend_unavailable_banner() -> None:
    ok, detail = _backend_health_probe()
    if ok:
        if detail.rstrip("/") != DEFAULT_BASE.rstrip("/"):
            st.warning(
                f"The API is running at **`{detail}`**, but this app is configured with "
                f"**`BACKEND_URL={DEFAULT_BASE}`** (unreachable). Sign-in and data calls will fail until they match.\n\n"
                f"**Fix:** stop Streamlit, then start again with e.g. `BACKEND_URL={detail} python run_pantryflow.py` "
                f"or unset `BACKEND_URL` to use the default `http://127.0.0.1:8000`.\n\n"
                + LAUNCH_HINT
            )
        return
    st.warning(
        "The Smart Pantry **API** is not reachable from this app, so sign-in and data views will not work until it is running.\n\n"
        f"Tried: {', '.join(_health_urls_to_try())} — last error: `{detail}`\n\n"
        + LAUNCH_HINT
        + "\n\n**If the web page itself would not load:** use **http://127.0.0.1:8501** on the same computer, "
        "or **http://YOUR-WIFI-IP:8501** from a phone (same Wi‑Fi). Restart after changing network."
    )
