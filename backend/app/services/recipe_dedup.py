"""Canonical recipe identity for deduplicating spellings and near-duplicate titles."""

from __future__ import annotations

import re
from typing import Any, Iterable, TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Recipe, ShoppingListItem
from app.services.recipe_image_match import name_similarity, norm_recipe_name
from app.services.recipe_image_urls import is_trusted_dish_image_url

# Same dish, alternate spellings (token-level).
_TOKEN_ALIASES: dict[str, str] = {
    "ghanoush": "ganoush",
    "ghannouj": "ganoush",
    "fettucine": "fettuccine",
    "houmous": "hummus",
    "hommus": "hummus",
    "humus": "hummus",
}

_DUPLICATE_SIMILARITY = 0.88


def canonical_recipe_key(name: str, cuisine: str = "") -> str:
    """Stable key for dedupe: cuisine + normalized title with spelling folds."""
    n = norm_recipe_name(name)
    n = re.sub(r"\bma\s+po\b", "mapo", n)
    n = re.sub(r"\balla\b", "", n)
    tokens = [_TOKEN_ALIASES.get(t, t) for t in n.split() if t]
    n = re.sub(r"\s+", " ", " ".join(tokens)).strip()
    cu = (cuisine or "").strip().lower()
    return f"{cu}::{n}" if cu else n


def recipes_are_duplicates(a_name: str, b_name: str, *, cuisine: str = "") -> bool:
    if canonical_recipe_key(a_name, cuisine) == canonical_recipe_key(b_name, cuisine):
        return True
    return name_similarity(a_name, b_name) >= _DUPLICATE_SIMILARITY


def _recipe_keep_score(recipe: Recipe) -> tuple[int, int, int]:
    img = 1 if is_trusted_dish_image_url(getattr(recipe, "image_url", None)) else 0
    steps = len((getattr(recipe, "structured_steps_json", None) or "") or "")
    return (img, steps, -int(recipe.id))


T = TypeVar("T")


def dedupe_recipe_dicts(
    items: Iterable[dict[str, Any]],
    *,
    id_field: str = "recipe_id",
    name_field: str = "name",
    cuisine_field: str = "cuisine",
) -> list[dict[str, Any]]:
    """Drop later items that share a canonical title with an earlier one."""
    seen_keys: set[str] = set()
    seen_ids: set[int] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            rid = int(it.get(id_field, 0) or 0)
        except (TypeError, ValueError):
            rid = 0
        name = str(it.get(name_field) or "").strip()
        cuisine = str(it.get(cuisine_field) or "").strip()
        ckey = canonical_recipe_key(name, cuisine)
        if not ckey or ckey in seen_keys:
            continue
        if rid > 0 and rid in seen_ids:
            continue
        seen_keys.add(ckey)
        if rid > 0:
            seen_ids.add(rid)
        out.append(it)
    return out


def dedupe_recipe_orm(rows: Iterable[Recipe]) -> list[Recipe]:
    """Keep the best row per canonical title (image + steps, then lowest id)."""
    buckets: dict[str, list[Recipe]] = {}
    for r in rows:
        key = canonical_recipe_key(r.name, r.cuisine)
        buckets.setdefault(key, []).append(r)
    out: list[Recipe] = []
    for group in buckets.values():
        out.append(max(group, key=_recipe_keep_score))
    return out


def remove_duplicate_recipes_from_db(db: Session) -> int:
    """Delete near-duplicate recipe rows; re-point shopping list FKs to the kept row."""
    rows = db.query(Recipe).order_by(Recipe.cuisine, Recipe.id).all()
    buckets: dict[str, list[Recipe]] = {}
    for r in rows:
        buckets.setdefault(canonical_recipe_key(r.name, r.cuisine), []).append(r)

    removed = 0
    for group in buckets.values():
        if len(group) < 2:
            continue
        group.sort(key=_recipe_keep_score, reverse=True)
        keep, *dupes = group
        for dup in dupes:
            db.query(ShoppingListItem).filter(ShoppingListItem.source_recipe_id == dup.id).update(
                {ShoppingListItem.source_recipe_id: keep.id},
                synchronize_session=False,
            )
            db.delete(dup)
            removed += 1
    if removed:
        db.commit()
    return removed
