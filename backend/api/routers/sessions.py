from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import (
    DocumentElement,
    SessionDetail,
    SessionSaveRequest,
    SessionSummary,
)
from .. import session_store

router = APIRouter()


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions():
    return [SessionSummary(**s) for s in session_store.list_sessions()]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    try:
        data = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    return SessionDetail(
        session_id=data["session_id"],
        name=data.get("name"),
        file_format=data["file_format"],
        original_filename=data["original_filename"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        rendered_html=data["rendered_html"],
        raw_text=data.get("raw_text", ""),
        document_structure=[DocumentElement(**e) for e in data["document_structure"]],
        placeholders=data["placeholders"],
        template_generated=data["template_generated"],
        outputs=data["outputs"],
        tex_pdf_url=data.get("tex_pdf_url"),
    )


@router.post("/sessions/{session_id}/save")
async def save_session(session_id: str, body: SessionSaveRequest):
    try:
        session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    session_store.update_session(session_id, updates)
    return {"ok": True}


@router.delete("/sessions/all")
async def delete_all_sessions():
    for s in session_store.list_sessions():
        session_store.delete_session(s["session_id"])
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    session_store.delete_session(session_id)
    return {"ok": True}
