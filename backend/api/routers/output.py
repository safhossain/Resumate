from __future__ import annotations

import html as html_mod
from pathlib import Path

import mammoth
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import session_store

router = APIRouter()


def _preview_html(output_path: Path, fmt: str) -> str:
    if fmt == "docx":
        with open(output_path, "rb") as fh:
            result = mammoth.convert_to_html(fh)
        return result.value
    if fmt == "txt":
        with open(output_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return f'<pre style="white-space:pre-wrap;">{html_mod.escape(text)}</pre>'
    return '<p>PDF output — use download.</p>'


@router.get("/output/{session_id}/{output_id}/preview")
async def preview_output(session_id: str, output_id: str):
    try:
        session = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    output = session_store.get_output(session_id, output_id)
    if output is None:
        raise HTTPException(404, "Output not found")

    output_path = Path(output["file_path"])
    if not output_path.exists():
        raise HTTPException(404, "Output file missing from disk")

    fmt = session["file_format"]

    if fmt == "tex":
        return FileResponse(output_path, media_type="application/pdf")

    return {"preview_html": _preview_html(output_path, fmt)}


@router.get("/output/{session_id}/{output_id}/download")
async def download_output(session_id: str, output_id: str):
    output = session_store.get_output(session_id, output_id)
    if output is None:
        raise HTTPException(404, "Output not found")

    output_path = Path(output["file_path"])
    if not output_path.exists():
        raise HTTPException(404, "Output file missing from disk")

    return FileResponse(output_path, filename=output_path.name)
