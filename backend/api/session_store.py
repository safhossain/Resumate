"""Thin persistence layer: read/write backend/sessions/{id}/session.json."""

from __future__ import annotations

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"


def _session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / session_id


def _session_file(session_id: str) -> Path:
    return _session_dir(session_id) / "session.json"


def _load(session_id: str) -> dict:
    path = _session_file(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id} not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(session_id: str, data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _session_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── public helpers ──────────────────────────────────────────────────


def get_session(session_id: str) -> dict:
    return _load(session_id)


def update_session(session_id: str, updates: dict) -> dict:
    data = _load(session_id)
    data.update(updates)
    _save(session_id, data)
    return data


def original_file_path(session_id: str) -> Path:
    data = _load(session_id)
    suffix_map = {"docx": ".docx", "txt": ".txt", "tex": ".tex"}
    suffix = suffix_map.get(data["file_format"], "")
    return _session_dir(session_id) / f"original{suffix}"


def template_file_path(session_id: str) -> Path:
    data = _load(session_id)
    fmt = data["file_format"]
    if fmt == "docx":
        return _session_dir(session_id) / "template.docx"
    if fmt == "txt":
        return _session_dir(session_id) / "template.txt.j2"
    if fmt == "tex":
        return _session_dir(session_id) / "template.tex.j2"
    raise ValueError(f"Unknown format: {fmt}")


def output_dir(session_id: str) -> Path:
    return _session_dir(session_id) / "outputs"


def add_placeholder(
    session_id: str,
    key: str,
    ptype: str,
    selected_text: str,
    start_offset: int,
    end_offset: int,
    value: Optional[str] = None,
) -> dict:
    data = _load(session_id)
    placeholder = {
        "key": key,
        "type": ptype,
        "selected_text": selected_text,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "value": value,
    }
    data["placeholders"][key] = placeholder
    data["template_generated"] = False
    _save(session_id, data)
    return placeholder


def rename_placeholder(session_id: str, old_key: str, new_key: str) -> dict:
    data = _load(session_id)
    phs = data["placeholders"]
    if old_key not in phs:
        raise KeyError(old_key)
    if new_key in phs:
        raise ValueError(f"Key '{new_key}' already exists")
    ph = phs.pop(old_key)
    ph["key"] = new_key
    phs[new_key] = ph
    data["template_generated"] = False
    _save(session_id, data)
    return ph


def update_placeholder_type(session_id: str, key: str, new_type: str) -> dict:
    data = _load(session_id)
    ph = data["placeholders"].get(key)
    if ph is None:
        raise KeyError(key)
    ph["type"] = new_type
    data["template_generated"] = False
    _save(session_id, data)
    return ph


def remove_placeholder(session_id: str, key: str) -> None:
    data = _load(session_id)
    data["placeholders"].pop(key, None)
    data["template_generated"] = False
    _save(session_id, data)


def add_output(session_id: str, output_info: dict) -> None:
    data = _load(session_id)
    data["outputs"].append(output_info)
    _save(session_id, data)


def get_output(session_id: str, output_id: str) -> Optional[dict]:
    data = _load(session_id)
    for out in data["outputs"]:
        if out["output_id"] == output_id:
            return out
    return None


def list_sessions() -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    sessions: list[dict] = []
    for sdir in sorted(SESSIONS_DIR.iterdir()):
        sf = sdir / "session.json"
        if not sf.exists():
            continue
        with open(sf, encoding="utf-8") as f:
            data = json.load(f)
        sessions.append(
            {
                "session_id": data["session_id"],
                "name": data.get("name"),
                "file_format": data["file_format"],
                "original_filename": data["original_filename"],
                "placeholder_count": len(data.get("placeholders", {})),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
            }
        )
    return sessions


def delete_session(session_id: str) -> None:
    sdir = _session_dir(session_id)
    if sdir.exists():
        shutil.rmtree(sdir)
