from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from ..models import PlaceholderCreate, PlaceholderResponse
from .. import session_store

router = APIRouter()


def _suggest_key(text: str, existing_keys: set[str]) -> str:
    """Heuristic key name based on selected text content."""
    stripped = text.strip()

    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", stripped):
        base = "email"
    elif re.search(r"(\+?\d[\d\s\-().]{7,})", stripped):
        base = "phone"
    elif len(stripped.split()) <= 4 and stripped.istitle():
        base = "name"
    elif stripped.lower().startswith(("skill", "technologies", "tech stack")):
        base = "skills"
    elif len(stripped) > 200:
        base = "summary"
    elif len(stripped.split()) <= 2:
        base = re.sub(r"\W+", "_", stripped.lower()).strip("_")[:20] or "field"
    else:
        words = stripped.split()[:3]
        base = "_".join(re.sub(r"\W+", "", w.lower()) for w in words if w)[:20] or "field"

    candidate = base
    counter = 2
    while candidate in existing_keys:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


@router.post("/placeholder", response_model=PlaceholderResponse)
async def add_placeholder(body: PlaceholderCreate):
    try:
        session = session_store.get_session(body.session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    raw_text = session.get("raw_text", "")

    if body.start_offset < 0 or body.end_offset > len(raw_text):
        raise HTTPException(400, "Offsets out of range")
    if body.start_offset >= body.end_offset:
        raise HTTPException(400, "Empty selection")

    actual_text = raw_text[body.start_offset : body.end_offset]
    if actual_text != body.selected_text:
        raise HTTPException(
            400,
            f"Selected text mismatch: expected {body.selected_text!r}, "
            f"found {actual_text!r} at offsets [{body.start_offset}:{body.end_offset}]",
        )

    # Check for overlapping placeholders
    for existing_ph in session["placeholders"].values():
        if _ranges_overlap(
            body.start_offset,
            body.end_offset,
            existing_ph["start_offset"],
            existing_ph["end_offset"],
        ):
            raise HTTPException(
                409,
                f"Selection overlaps with existing placeholder '{existing_ph['key']}'",
            )

    existing_keys = set(session["placeholders"].keys())
    key = body.key or _suggest_key(body.selected_text, existing_keys)

    if key in existing_keys:
        raise HTTPException(409, f"Key '{key}' already exists")

    ph = session_store.add_placeholder(
        session_id=body.session_id,
        key=key,
        ptype=body.type,
        selected_text=body.selected_text,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
        value=body.value,
    )

    return PlaceholderResponse(
        key=ph["key"],
        type=ph["type"],
        selected_text=ph["selected_text"],
        start_offset=ph["start_offset"],
        end_offset=ph["end_offset"],
        value=ph.get("value"),
    )


@router.patch("/placeholder/{session_id}/{key}/type")
async def update_placeholder_type(session_id: str, key: str, new_type: str):
    if new_type not in ("tailor", "sensitive"):
        raise HTTPException(400, f"Invalid type: {new_type!r}")
    try:
        ph = session_store.update_placeholder_type(session_id, key, new_type)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    except KeyError:
        raise HTTPException(404, f"Placeholder '{key}' not found")
    return PlaceholderResponse(
        key=ph["key"],
        type=ph["type"],
        selected_text=ph["selected_text"],
        start_offset=ph["start_offset"],
        end_offset=ph["end_offset"],
        value=ph.get("value"),
    )


@router.delete("/placeholder/{session_id}/{key}")
async def delete_placeholder(session_id: str, key: str):
    try:
        session = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if key not in session["placeholders"]:
        raise HTTPException(404, f"Placeholder '{key}' not found")

    session_store.remove_placeholder(session_id, key)
    return {"ok": True}
