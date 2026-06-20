"""Google Sheets access layer for Macro Traco.

The Sheet is the single source of truth. This module reads it, derives the
unique-value lists that power the autocomplete dropdowns, and appends new rows
with live formulas in the calculated columns.

Auth uses a Google service account. Provide credentials via either:
  - GOOGLE_SERVICE_ACCOUNT_JSON : the raw JSON key contents (preferred on Render)
  - GOOGLE_APPLICATION_CREDENTIALS : path to a service_account.json file
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

from app.calc import formulas_for_row

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Header -> column index (0-based) in the order they appear in the sheet.
HEADERS = [
    "Food Item", "Store", "Brand", "Category", "Form Factor", "Date",
    "Price ($)", "Size", "Serving Size", "Protein / serving", "Calories / Unit",
    "$ / 30g protein", "Calories / 30g", "Serving size / 30g", "Rank",
]

# Columns the user fills in vs. columns the sheet computes.
USER_TEXT_FIELDS = ["Food Item", "Store", "Brand", "Category", "Form Factor", "Date"]
USER_NUMERIC_FIELDS = ["Price ($)", "Size", "Serving Size", "Protein / serving", "Calories / Unit"]
# Fields offered as dynamic autocomplete dropdowns (exclude free-text Food Item / Date).
DROPDOWN_FIELDS = ["Store", "Brand", "Category", "Form Factor"]


def _credentials() -> Credentials:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=SCOPES)


@lru_cache(maxsize=1)
def _client() -> gspread.Client:
    return gspread.authorize(_credentials())


def _worksheet():
    sheet_id = os.environ["SHEET_ID"]
    ws_name = os.environ.get("WORKSHEET_NAME", "")
    spreadsheet = _client().open_by_key(sheet_id)
    if ws_name:
        return spreadsheet.worksheet(ws_name)
    return spreadsheet.sheet1


def read_rows() -> list[dict]:
    """Return all data rows as dicts keyed by header. Computed columns included."""
    ws = _worksheet()
    records = ws.get_all_records(expected_headers=HEADERS)
    return records


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def existing_values() -> dict[str, list[float | None]]:
    """Pull the columns needed for comparison/analysis as parsed numbers."""
    rows = read_rows()
    return {
        "dollars_per_30g": [_to_float(r.get("$ / 30g protein")) for r in rows],
    }


def dropdown_options() -> dict[str, list[str]]:
    """Unique, sorted, non-empty values for each autocomplete field."""
    rows = read_rows()
    options: dict[str, list[str]] = {}
    for field in DROPDOWN_FIELDS:
        seen = {str(r.get(field, "")).strip() for r in rows}
        seen.discard("")
        options[field] = sorted(seen, key=str.lower)
    return options


def append_entry(entry: dict) -> dict:
    """Append a new row. User columns are written as values; the four calculated
    columns are written as live formulas so the Sheet computes them itself.

    `entry` keys are the HEADERS for USER_TEXT_FIELDS + USER_NUMERIC_FIELDS.
    Returns the row number that was written.
    """
    ws = _worksheet()
    existing = ws.get_all_values()  # includes header row
    next_row = len(existing) + 1     # 1-based row index for the new entry

    formulas = formulas_for_row(next_row)
    row_values = []
    for header in HEADERS:
        col_letter = chr(ord("A") + HEADERS.index(header))
        if col_letter in formulas:
            row_values.append(formulas[col_letter])
        else:
            row_values.append(entry.get(header, ""))

    ws.update(
        f"A{next_row}:O{next_row}",
        [row_values],
        value_input_option="USER_ENTERED",
    )
    return {"row": next_row}
