from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.parsers_and_generators.brace_utils import brace_balance
from ..models import PlaceholderCreate, PlaceholderResize, PlaceholderResponse
from .. import session_store

router = APIRouter()


class PlaceholderReorderRequest(BaseModel):
    ordered_keys: list[str]

# ── key sanitization ────────────────────────────────────────────────

_INVALID_CHARS = re.compile(r"[^a-z0-9_]")
_MULTI_UNDER  = re.compile(r"_+")

def sanitize_key(raw: str) -> str:
    """Return a lowercase identifier: only a-z, 0-9, underscore; no leading/trailing underscores."""
    s = raw.lower()
    s = s.replace("-", "_").replace(" ", "_")
    s = _INVALID_CHARS.sub("_", s)
    s = _MULTI_UNDER.sub("_", s)
    return s.strip("_") or "field"


# ── YAKE-backed auto-naming ─────────────────────────────────────────

# Fast structural detectors that beat keyword extraction for known patterns
_RE_EMAIL   = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_PHONE   = re.compile(r"(\+?\d[\d\s\-().]{7,})")
_RE_URL     = re.compile(r"https?://|www\.|linkedin\.com|github\.com", re.I)
_RE_LABELED = re.compile(r"^([^:]{1,40}):", re.I)   # "Frameworks: …"

# YAKE extractor – instantiated once, thread-safe for reads
try:
    import yake as _yake
    _YAKE = _yake.KeywordExtractor(lan="en", n=2, dedupLim=0.7, top=3, features=None)
except Exception:
    _YAKE = None


def _yake_base(text: str) -> str | None:
    if _YAKE is None:
        return None
    try:
        kws = _YAKE.extract_keywords(text)
        if not kws:
            return None
        best = min(kws, key=lambda x: x[1])[0]
        return sanitize_key(best)[:30] or None
    except Exception:
        return None


def _suggest_key(text: str, existing_keys: set[str]) -> str:
    stripped = text.strip()

    # ── fast structural checks (no model needed) ──────────────────
    if _RE_EMAIL.search(stripped):
        base = "email"
    elif _RE_PHONE.search(stripped):
        base = "phone"
    elif _RE_URL.search(stripped):
        # Turn URL path into a slug: strip protocol, swap / and - for _
        slug = re.sub(r"https?://", "", stripped.lower())
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")[:30]
        base = slug or "url"
    elif m := _RE_LABELED.match(stripped):
        # "Frameworks and Libraries: …" → "frameworks_and_libraries"
        base = sanitize_key(m.group(1))[:30] or "field"
    elif len(stripped) > 300:
        base = "summary"
    else:
        # ── YAKE keyword extraction ───────────────────────────────
        ybase = _yake_base(stripped)
        if ybase:
            base = ybase
        else:
            # Fallback: first 3 words slugified
            words = stripped.split()[:3]
            base = sanitize_key(" ".join(words))[:30] or "field"

    # ── uniqueness suffix ─────────────────────────────────────────
    candidate = base
    counter = 2
    while candidate in existing_keys:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _tex_brace_warning(session: dict, text: str) -> str | None:
    """Non-blocking advisory when a .tex selection has unbalanced braces."""
    if session.get("file_format") != "tex":
        return None
    balance = brace_balance(text)
    if balance > 0:
        return (
            f"Selection has {balance} unclosed '{{' — this may cause LaTeX rendering errors. "
            "Consider adjusting your selection to exclude the opening brace(s)."
        )
    if balance < 0:
        return (
            f"Selection has {-balance} extra '}}' — this may cause LaTeX rendering errors. "
            "Consider adjusting your selection to exclude the trailing brace(s)."
        )
    return None


def _ph_response(ph: dict, warning: str | None = None) -> PlaceholderResponse:
    """Build a PlaceholderResponse from a stored placeholder dict."""
    return PlaceholderResponse(
        key=ph["key"],
        type=ph["type"],
        selected_text=ph["selected_text"],
        start_offset=ph["start_offset"],
        end_offset=ph["end_offset"],
        value=ph.get("value"),
        warning=warning,
    )


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

    # For .tex files, flag selections with unbalanced curly braces.
    # This is non-blocking (placeholder is still created) but a warning is returned
    # so the frontend can show an amber advisory to the user.
    tex_warning = _tex_brace_warning(session, actual_text)

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
    if body.key:
        key = sanitize_key(body.key)
        if not key:
            raise HTTPException(400, "Key is empty after sanitization")
    else:
        key = _suggest_key(body.selected_text, existing_keys)

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

    return _ph_response(ph, warning=tex_warning)


@router.patch("/placeholder/{session_id}/reorder")
async def reorder_placeholders(session_id: str, body: PlaceholderReorderRequest):
    try:
        session = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    existing = set(session["placeholders"].keys())
    incoming = list(body.ordered_keys)
    if len(incoming) != len(set(incoming)):
        raise HTTPException(400, "ordered_keys contains duplicates")
    if set(incoming) != existing:
        raise HTTPException(
            400, "ordered_keys must contain exactly the existing placeholder keys"
        )

    session_store.reorder_placeholders(session_id, incoming)
    return {"ok": True}


@router.patch("/placeholder/{session_id}/{key}/resize", response_model=PlaceholderResponse)
async def resize_placeholder(session_id: str, key: str, body: PlaceholderResize):
    """Move a placeholder's start/end boundary to a new pair of offsets.

    Rejects (409) when the new range overlaps a *different* placeholder — this
    is what backs the drag-handle "drop onto another placeholder" failure.
    """
    try:
        session = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    phs = session["placeholders"]
    if key not in phs:
        raise HTTPException(404, f"Placeholder '{key}' not found")

    raw_text = session.get("raw_text", "")
    start, end = body.start_offset, body.end_offset
    if start < 0 or end > len(raw_text):
        raise HTTPException(400, "Offsets out of range")
    if start >= end:
        raise HTTPException(400, "Empty selection")

    for other_key, other in phs.items():
        if other_key == key:
            continue
        if _ranges_overlap(start, end, other["start_offset"], other["end_offset"]):
            raise HTTPException(
                409,
                f"Selection overlaps with existing placeholder '{other['key']}'",
            )

    new_text = raw_text[start:end]

    # Keep `value` tracking the highlight when it was an unedited copy of the
    # old captured text; preserve a genuinely customized value otherwise.
    current = phs[key]
    cur_val = current.get("value")
    new_val = new_text if (cur_val is not None and cur_val == current.get("selected_text")) else None

    tex_warning = _tex_brace_warning(session, new_text)

    ph = session_store.resize_placeholder(
        session_id=session_id,
        key=key,
        start_offset=start,
        end_offset=end,
        selected_text=new_text,
        value=new_val,
    )

    return _ph_response(ph, warning=tex_warning)


@router.patch("/placeholder/{session_id}/{key}/rename")
async def rename_placeholder(session_id: str, key: str, new_key: str):
    clean = sanitize_key(new_key)
    if not clean:
        raise HTTPException(400, "New key is empty after sanitization")
    try:
        ph = session_store.rename_placeholder(session_id, key, clean)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    except KeyError:
        raise HTTPException(404, f"Placeholder '{key}' not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return _ph_response(ph)


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
    return _ph_response(ph)


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
