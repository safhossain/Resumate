from __future__ import annotations

import html as html_mod
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models import DocumentElement, UploadResponse
from .. import session_store

router = APIRouter()


def _text_to_inner_html(text: str) -> str:
    """HTML-escape then convert \\t and \\n to elements the browser preserves
    in Range.toString(), so character offsets stay in sync with raw_text."""
    if not text:
        return "&nbsp;"
    h = html_mod.escape(text)
    h = h.replace("\t", '<span class="docx-tab">\t</span>')
    h = h.replace("\n", "<br>")
    return h


# ── DOCX processing ────────────────────────────────────────────────


def _process_docx(file_path: Path) -> tuple[str, list[dict], str]:
    from docx import Document

    doc = Document(str(file_path))
    html_parts: list[str] = []
    structure: list[dict] = []
    offset = 0

    for i, para in enumerate(doc.paragraphs):
        text = para.text
        inner = _text_to_inner_html(text)

        style_name = (para.style.name or "").lower()
        extra_cls = ""
        if "heading 1" in style_name:
            extra_cls = " resume-h1"
        elif "heading 2" in style_name:
            extra_cls = " resume-h2"
        elif "heading 3" in style_name:
            extra_cls = " resume-h3"

        # Detect bullet/numbered paragraphs via <w:numPr> — purely visual flag.
        _WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        _pPr = para._p.find(f"{{{_WNS}}}pPr")
        if _pPr is not None and _pPr.find(f"{{{_WNS}}}numPr") is not None:
            extra_cls += " resume-bullet"

        elem_id = f"p_{i}"
        html_parts.append(
            f'<div data-element-id="{elem_id}" data-offset="{offset}"'
            f' class="resume-element{extra_cls}">{inner}</div>'
        )
        structure.append(
            {"id": elem_id, "type": "paragraph", "text": text, "offset": offset}
        )
        offset += len(text) + 1  # +1 for the \n joining paragraphs

    raw_text = "\n".join(s["text"] for s in structure)
    return "\n".join(html_parts), structure, raw_text


# ── line-based processing (TXT + TEX) ──────────────────────────────


def _process_lines(file_path: Path, extra_class: str = "") -> tuple[str, list[dict], str]:
    """Render a plain-text/line-based file to per-line offset-tagged divs.

    *extra_class* appends an extra CSS class to each line div (e.g. ``tex-line``).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    structure: list[dict] = []
    html_parts: list[str] = []
    offset = 0
    cls = "resume-element resume-line" + (f" {extra_class}" if extra_class else "")

    for i, line_text in enumerate(lines):
        inner = _text_to_inner_html(line_text)
        elem_id = f"line_{i}"
        html_parts.append(
            f'<div data-element-id="{elem_id}" data-offset="{offset}"'
            f' class="{cls}">{inner}</div>'
        )
        structure.append(
            {"id": elem_id, "type": "line", "text": line_text, "offset": offset}
        )
        offset += len(line_text) + 1  # +1 for \n

    return "\n".join(html_parts), structure, content


def _process_txt(file_path: Path) -> tuple[str, list[dict], str]:
    return _process_lines(file_path)


def _process_tex(file_path: Path) -> tuple[str, list[dict], str, str | None]:
    rendered_html, structure, content = _process_lines(file_path, extra_class="tex-line")

    tex_pdf_url: str | None = None
    try:
        from backend.parsers_and_generators.tex_to_pdf import gen_pdf

        pdf_path = gen_pdf(file_path, file_path.parent)
        sid = file_path.parent.name
        tex_pdf_url = f"/api/static/sessions/{sid}/{pdf_path.name}"
    except Exception:
        pass

    return rendered_html, structure, content, tex_pdf_url


# ── endpoint ───────────────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    if suffix not in (".docx", ".txt", ".tex"):
        raise HTTPException(
            400,
            f"Unsupported file type: {suffix}. Accepted: .docx, .txt, .tex",
        )

    format_map = {".docx": "docx", ".txt": "txt", ".tex": "tex"}
    file_format = format_map[suffix]

    import uuid
    from datetime import datetime, timezone

    temp_id = uuid.uuid4().hex[:12]
    sdir = session_store.SESSIONS_DIR / temp_id
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "outputs").mkdir(exist_ok=True)

    original_path = sdir / f"original{suffix}"
    content = await file.read()
    with open(original_path, "wb") as f:
        f.write(content)

    tex_pdf_url: str | None = None
    try:
        if file_format == "docx":
            rendered_html, structure, raw_text = _process_docx(original_path)
        elif file_format == "txt":
            rendered_html, structure, raw_text = _process_txt(original_path)
        else:
            rendered_html, structure, raw_text, tex_pdf_url = _process_tex(
                original_path
            )
    except Exception as exc:
        import shutil

        shutil.rmtree(sdir, ignore_errors=True)
        raise HTTPException(500, f"Failed to process file: {exc}") from exc

    now = datetime.now(timezone.utc).isoformat()
    session_data = {
        "session_id": temp_id,
        "name": None,
        "file_format": file_format,
        "original_filename": filename,
        "created_at": now,
        "updated_at": now,
        "document_structure": structure,
        "rendered_html": rendered_html,
        "raw_text": raw_text,
        "tex_pdf_url": tex_pdf_url,
        "placeholders": {},
        "template_generated": False,
        "outputs": [],
    }
    session_store._save(temp_id, session_data)

    return UploadResponse(
        session_id=temp_id,
        rendered_html=rendered_html,
        raw_text=raw_text,
        document_structure=[DocumentElement(**s) for s in structure],
        file_format=file_format,
        tex_pdf_url=tex_pdf_url,
    )
