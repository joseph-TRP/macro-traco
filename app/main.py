"""Macro Traco — FastAPI backend.

Serves the two-screen SPA and exposes a small JSON API over the Google Sheet:
  GET  /                  -> the app shell
  GET  /api/version       -> current version string
  GET  /api/options       -> dynamic dropdown values for the entry form
  GET  /api/data          -> all rows (powers the dashboard)
  POST /api/quick-compare -> rank a hypothetical item without saving it
  POST /api/entries       -> append a new row to the sheet
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of the process working directory
# (the preview/launch runner may start us from a different cwd).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import sheets
from app.calc import compute_stats, rank_against
from app.version import bump, get_version

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Macro Traco")

# Cache the version once at startup; bump on deploy if explicitly enabled.
_VERSION = get_version()


@app.on_event("startup")
def _startup() -> None:
    global _VERSION
    # BUMP_VERSION_ON_START is set on the Render service so each deploy ticks the
    # patch number exactly once. Locally it stays off so dev restarts don't bump.
    if os.environ.get("BUMP_VERSION_ON_START", "").lower() in ("1", "true", "yes"):
        _VERSION = bump(os.environ.get("DEPLOY_NOTE", ""))
    else:
        _VERSION = get_version()


# ---- Models -----------------------------------------------------------------

class CompareInput(BaseModel):
    food_item: str = Field(..., min_length=1)
    category: str | None = None
    price: float
    size: float
    serving_size: float
    protein: float
    calories: float


class EntryInput(CompareInput):
    store: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1)
    form_factor: str = Field(..., min_length=1)
    date: str = Field(..., min_length=1)


# ---- API --------------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe for Render's router. Deliberately does NOT touch Google so
    health stays green regardless of Sheets API latency."""
    return {"status": "ok"}


@app.get("/api/version")
def api_version() -> dict:
    return {"version": _VERSION}


@app.get("/api/options")
def api_options() -> dict:
    try:
        return sheets.dropdown_options()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sheet read failed: {exc}")


@app.get("/api/data")
def api_data() -> dict:
    try:
        return {"rows": sheets.read_rows()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sheet read failed: {exc}")


def _compare(inp: CompareInput) -> dict:
    try:
        stats = compute_stats(inp.price, inp.size, inp.serving_size, inp.protein, inp.calories)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    rows = sheets.read_rows()
    values = [sheets._to_float(r.get("$ / 30g protein")) for r in rows]
    overall = rank_against(stats.dollars_per_30g, values)

    # Category-specific ranking.
    category = (inp.category or "").strip().lower()
    cat_values = [
        sheets._to_float(r.get("$ / 30g protein"))
        for r in rows
        if str(r.get("Category", "")).strip().lower() == category and category
    ]
    category_rank = rank_against(stats.dollars_per_30g, cat_values) if cat_values else None

    # Neighbours: the items just better and just worse on $/30g.
    enriched = []
    for r in rows:
        v = sheets._to_float(r.get("$ / 30g protein"))
        if v is not None and v > 0:
            enriched.append((v, r))
    enriched.sort(key=lambda t: t[0])
    insert_at = sum(1 for v, _ in enriched if v < stats.dollars_per_30g)
    window = enriched[max(0, insert_at - 3): insert_at + 3]
    neighbors = [
        {
            "food_item": r.get("Food Item"),
            "store": r.get("Store"),
            "brand": r.get("Brand"),
            "category": r.get("Category"),
            "dollars_per_30g": v,
            "calories_per_30g": sheets._to_float(r.get("Calories / 30g")),
        }
        for v, r in window
    ]

    return {
        "stats": {
            "dollars_per_30g": stats.dollars_per_30g,
            "calories_per_30g": stats.calories_per_30g,
            "serving_size_per_30g": stats.serving_size_per_30g,
        },
        "overall": overall,
        "category": inp.category,
        "category_rank": category_rank,
        "neighbors": neighbors,
        "insert_at": insert_at,
    }


@app.post("/api/quick-compare")
def api_quick_compare(inp: CompareInput) -> dict:
    return _compare(inp)


@app.post("/api/entries")
def api_add_entry(inp: EntryInput) -> dict:
    result = _compare(inp)  # also validates numerics
    entry = {
        "Food Item": inp.food_item,
        "Store": inp.store,
        "Brand": inp.brand,
        "Category": inp.category or "",
        "Form Factor": inp.form_factor,
        "Date": inp.date,
        "Price ($)": inp.price,
        "Size": inp.size,
        "Serving Size": inp.serving_size,
        "Protein / serving": inp.protein,
        "Calories / Unit": inp.calories,
    }
    try:
        written = sheets.append_entry(entry)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sheet write failed: {exc}")
    return {"ok": True, "row": written["row"], "compare": result}


# ---- Static SPA (mounted last so /api/* wins) -------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
