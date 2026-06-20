"""App version counter, stored as a text file in the project's Google Drive folder.

Per spec: the version lives in the cloud (not local storage), is dev-style
(vX.YY.Z), auto-increments on each deploy, and can carry a one-line commit note.
It is purely cosmetic — shown in light grey at the bottom of the app.

Format of the Drive text file (single line):
    v0.1.3 | added dashboard filters

`bump()` is intended to run once per deploy (called at app startup). It
increments the patch number and optionally records a note.
"""

from __future__ import annotations

import io
import os

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from app.sheets import _credentials

VERSION_FILENAME = "version.txt"
_DEFAULT = "v0.0.0"


def _drive():
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _find_file(service) -> str | None:
    folder = os.environ["DRIVE_FOLDER_ID"]
    q = f"name = '{VERSION_FILENAME}' and '{folder}' in parents and trashed = false"
    res = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _read_raw(service, file_id: str) -> str:
    data = service.files().get_media(fileId=file_id).execute()
    return data.decode("utf-8").strip() if isinstance(data, bytes) else str(data).strip()


def _write_raw(service, file_id: str | None, content: str) -> str:
    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="text/plain")
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        return file_id
    meta = {"name": VERSION_FILENAME, "parents": [os.environ["DRIVE_FOLDER_ID"]]}
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created["id"]


def _parse(line: str) -> tuple[tuple[int, int, int], str]:
    """'v0.1.3 | note' -> ((0, 1, 3), 'note')."""
    version, _, note = line.partition("|")
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
        service = _drive()
        file_id = _find_file(service)
        if not file_id:
            return _DEFAULT
        (major, minor, patch), _ = _parse(_read_raw(service, file_id))
        return f"v{major}.{minor}.{patch}"
    except Exception:
        return _DEFAULT


def bump(note: str = "") -> str:
    """Increment the patch version and persist it. Returns the new version.
    Resilient: on any failure it logs and returns the default rather than
    blocking app startup."""
    try:
        service = _drive()
        file_id = _find_file(service)
        current = _read_raw(service, file_id) if file_id else _DEFAULT
        (major, minor, patch), prev_note = _parse(current)
        patch += 1
        new_version = f"v{major}.{minor}.{patch}"
        line = f"{new_version} | {note}" if note else f"{new_version} | {prev_note}".rstrip(" |")
        _write_raw(service, file_id, line)
        return new_version
    except Exception as exc:  # pragma: no cover - cosmetic feature, must not crash app
        print(f"[version] bump skipped: {exc}")
        return _DEFAULT
