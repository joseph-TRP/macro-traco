"""App version counter, stored in a hidden '_meta' tab of the database spreadsheet.

Cloud-only (lives in the same Google Sheet — no local storage, no Drive API).
Dev-style vX.Y.Z, auto-increments the patch on each deploy, with an optional
one-line note. Purely cosmetic — shown in grey at the bottom of the app.

Stored in cell A1 of the '_meta' tab as a single line:  'v0.1.3 | added filters'
"""

from __future__ import annotations

import os

import gspread

from app.sheets import _client

META_TAB = "_meta"
_DEFAULT = "v0.0.0"


def _meta_ws():
    ss = _client().open_by_key(os.environ["SHEET_ID"])
    try:
        return ss.worksheet(META_TAB)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=META_TAB, rows=2, cols=2)
        ws.update_acell("A1", _DEFAULT)
        return ws


def _parse(line: str) -> tuple[tuple[int, int, int], str]:
    """'v0.1.3 | note' -> ((0, 1, 3), 'note')."""
    version, _, note = (line or "").partition("|")
    note = note.strip()
    nums = version.strip().lstrip("vV").split(".")
    try:
        major, minor, patch = (int(nums[0]), int(nums[1]), int(nums[2]))
    except (ValueError, IndexError):
        major, minor, patch = (0, 0, 0)
    return (major, minor, patch), note


def get_version() -> str:
    """Return the current version string (e.g. 'v0.1.3'). Never raises."""
    try:
        line = _meta_ws().acell("A1").value or _DEFAULT
        (major, minor, patch), _ = _parse(line)
        return f"v{major}.{minor}.{patch}"
    except Exception:
        return _DEFAULT


def bump(note: str = "") -> str:
    """Increment the patch version and persist it. Returns the new version.
    Resilient: on any failure it logs and returns the default rather than
    blocking app startup."""
    try:
        ws = _meta_ws()
        line = ws.acell("A1").value or _DEFAULT
        (major, minor, patch), prev_note = _parse(line)
        patch += 1
        new_version = f"v{major}.{minor}.{patch}"
        out = f"{new_version} | {note}" if note else f"{new_version} | {prev_note}".rstrip(" |")
        ws.update_acell("A1", out)
        return new_version
    except Exception as exc:  # pragma: no cover - cosmetic feature, must not crash app
        print(f"[version] bump skipped: {exc}")
        return _DEFAULT
