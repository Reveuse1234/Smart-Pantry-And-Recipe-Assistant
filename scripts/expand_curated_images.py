#!/usr/bin/env python3
"""Find strict dish photos for catalog recipes and merge into curated_dish_images.json."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.dish_image_datasets import (  # noqa: E402
    _catalog_dir,
    _exact_key,
    lookup_dish_image,
    reload_dataset_index,
)
from app.services.recipe_image_urls import public_dish_image_url  # noqa: E402
from app.services.themealdb import thumb_for_recipe  # noqa: E402
from app.services.wikimedia_images import (  # noqa: E402
    wikimedia_loose_for_recipe,
    wikimedia_thumb_for_recipe,
)

CATALOG_FILES = {
    "Kashmiri": "kashmiri.json",
    "Indian": "indian.json",
    "Italian": "italian.json",
    "Chinese": "chinese.json",
    "Middle Eastern": "middle_eastern.json",
}


def _collect_recipes() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for cuisine, fname in CATALOG_FILES.items():
        path = _catalog_dir() / fname
        if not path.is_file():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            key = _exact_key(name, cuisine)
            if name and key not in seen:
                seen.add(key)
                out.append((name, cuisine))
    return out


def _find_url(name: str, cuisine: str) -> str:
    for fn in (
        lambda: thumb_for_recipe(name, cuisine),
        lambda: wikimedia_thumb_for_recipe(name, cuisine),
        lambda: wikimedia_loose_for_recipe(name, cuisine),
    ):
        url = fn()
        if public_dish_image_url(url):
            return url or ""
        time.sleep(0.04)
    return ""


def _reject_bad_match(key: str, url: str) -> bool:
    """Return True when the URL should not be stored for this dish."""
    from app.services.recipe_image_urls import is_blocked_dish_image_url

    if is_blocked_dish_image_url(url):
        return True
    low = url.lower()
    dish = key.split("::", 1)[-1]
    # Single-token dish names must not match person surnames in the filename.
    if " " not in dish and any(x in low for x in (",", "dpla", "portrait", "born")):
        return True
    return False


def main() -> int:
    curated_path = ROOT / "data" / "datasets" / "curated_dish_images.json"
    curated = json.loads(curated_path.read_text(encoding="utf-8"))
    by_exact: dict[str, str] = dict(curated.get("by_exact") or {})
    reload_dataset_index()

    added = 0
    skipped = 0
    still_missing: list[str] = []

    for name, cuisine in _collect_recipes():
        key = _exact_key(name, cuisine)
        if public_dish_image_url(lookup_dish_image(name, cuisine)):
            skipped += 1
            continue
        if public_dish_image_url(by_exact.get(key)):
            continue
        print(f"Searching: {cuisine} — {name} …", flush=True)
        url = _find_url(name, cuisine)
        if url and not _reject_bad_match(key, url):
            by_exact[key] = url
            added += 1
            print(f"  + {url[:72]}…", flush=True)
        else:
            still_missing.append(key)
            print("  (no match)", flush=True)
        time.sleep(0.06)

    curated["by_exact"] = by_exact
    curated["version"] = int(curated.get("version") or 1) + 1
    curated_path.write_text(json.dumps(curated, indent=2) + "\n", encoding="utf-8")
    print(f"\nAdded {added} new curated images; already had {skipped}; still missing {len(still_missing)}")
    if still_missing:
        print("No photo found for:")
        for line in still_missing:
            print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
