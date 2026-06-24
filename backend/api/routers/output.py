from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import session_store
from ..preview import render_preview_html

router = APIRouter()


def _get_output_or_404(session_id: str, output_id: str) -> dict:
    output = session_store.get_output(session_id, output_id)
    if output is None:
        raise HTTPException(404, "Output not found")
    return output


@router.get("/output/{session_id}/{output_id}/preview")
async def preview_output(session_id: str, output_id: str):
    try:
        session = session_store.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    output = _get_output_or_404(session_id, output_id)
    output_path = Path(output["file_path"])
    if not output_path.exists():
        raise HTTPException(404, "Output file missing from disk")

    fmt = session["file_format"]
    if fmt == "tex":
        return FileResponse(output_path, media_type="application/pdf")
    return {"preview_html": render_preview_html(output_path, fmt)}


@router.get("/output/{session_id}/{output_id}/download")
async def download_output(session_id: str, output_id: str):
    """Legacy single-file download — returns the final/latest output file."""
    output = _get_output_or_404(session_id, output_id)
    output_path = Path(output["file_path"])
    if not output_path.exists():
        raise HTTPException(404, "Output file missing from disk")
    return FileResponse(output_path, filename=output_path.name)


# ── Per-stage download endpoints ────────────────────────────────────
#
# stage: "initial" | "auto_retry" | "manual_retry"
# For tex outputs each stage has a .pdf and a .tex source file.
# For other formats only the main output file exists.
#
# Path map stored in output_info:
#   initial   → initial_file_path  / initial_tex_path
#   auto_retry / manual_retry → file_path / tex_path

def _resolve_stage_paths(output: dict, stage: str) -> tuple[Path | None, Path | None]:
    """Return (pdf_path, tex_path) for the requested stage, or (None, None)."""
    if stage == "initial":
        pdf_raw = output.get("initial_file_path") or output.get("file_path")
        tex_raw = output.get("initial_tex_path") or output.get("tex_path")
    else:
        # auto_retry and manual_retry both store their output as the primary file_path
        pdf_raw = output.get("file_path")
        tex_raw = output.get("tex_path")

    pdf_path = Path(pdf_raw) if pdf_raw else None
    tex_path = Path(tex_raw) if tex_raw else None
    return pdf_path, tex_path


@router.get("/output/{session_id}/{output_id}/download/stage/{stage}")
async def download_stage_pdf(session_id: str, output_id: str, stage: str):
    """Download the PDF (or docx/txt) for a specific pipeline stage."""
    output = _get_output_or_404(session_id, output_id)
    pdf_path, _ = _resolve_stage_paths(output, stage)
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(404, f"No PDF file found for stage '{stage}'")
    return FileResponse(pdf_path, filename=pdf_path.name)


@router.get("/output/{session_id}/{output_id}/download/stage/{stage}/tex")
async def download_stage_tex(session_id: str, output_id: str, stage: str):
    """Download the .tex source for a specific pipeline stage."""
    output = _get_output_or_404(session_id, output_id)
    _, tex_path = _resolve_stage_paths(output, stage)
    if not tex_path or not tex_path.exists():
        raise HTTPException(404, f"No .tex source file found for stage '{stage}'")
    return FileResponse(tex_path, filename=tex_path.name, media_type="text/x-tex")
