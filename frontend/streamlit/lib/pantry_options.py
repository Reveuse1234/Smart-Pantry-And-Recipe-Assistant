"""Pantry unit and category choices for Ingredients UI."""

from __future__ import annotations

import streamlit as st

# Aligned with recipe catalog units plus common grocery measures.
PANTRY_UNITS: tuple[str, ...] = (
    "each",
    "g",
    "kg",
    "ml",
    "L",
    "cup",
    "cups",
    "tbsp",
    "tsp",
    "oz",
    "lb",
    "pinch",
    "cloves",
    "slices",
    "stalks",
    "stick",
    "leaves",
    "pods",
    "large",
    "inch",
    "g canned",
    "g cooked",
    "g dry",
)

PANTRY_CATEGORIES: tuple[str, ...] = (
    "general",
    "produce",
    "dairy",
    "meat & seafood",
    "bakery",
    "grains & dry goods",
    "canned & jarred",
    "spices & seasonings",
    "frozen",
    "beverages",
    "snacks",
    "condiments & sauces",
    "other",
)


def select_options_with_current(
    options: tuple[str, ...],
    current: str | None,
    *,
    default: str,
) -> tuple[list[str], int]:
    """Build selectbox options, preserving an unknown current value at the top."""
    cur = (current or default).strip() or default
    opts = list(options)
    if cur not in opts:
        opts = [cur] + opts
    return opts, opts.index(cur)


def pantry_unit_selectbox(
    label: str = "Unit",
    *,
    value: str = "each",
    key: str | None = None,
    label_visibility: str = "visible",
) -> str:
    opts, idx = select_options_with_current(PANTRY_UNITS, value, default="each")
    kwargs: dict = {
        "label": label,
        "options": opts,
        "index": idx,
        "label_visibility": label_visibility,
    }
    if key:
        kwargs["key"] = key
    return st.selectbox(**kwargs)


def pantry_category_selectbox(
    label: str = "Category",
    *,
    value: str = "general",
    key: str | None = None,
    label_visibility: str = "visible",
) -> str:
    opts, idx = select_options_with_current(PANTRY_CATEGORIES, value, default="general")
    kwargs: dict = {
        "label": label,
        "options": opts,
        "index": idx,
        "label_visibility": label_visibility,
    }
    if key:
        kwargs["key"] = key
    return st.selectbox(**kwargs)
