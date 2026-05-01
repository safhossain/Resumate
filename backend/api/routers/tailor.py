"""Template generation, tailoring (LLM pipeline), and retry endpoints."""

from __future__ import annotations

import html as html_mod
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import mammoth
from fastapi import APIRouter, HTTPException

from backend.llm_integration.AI_API.api_scripts.contracts import LLM_I, MOD_DEG
from backend.llm_integration.LLM_CALL import (
    CALL,
    CALL_RETRY,
    CALL_RETRY_TEX,
    CALL_RETRY2,
    CALL_RETRY2_TEX,
    DEFAULT_MODEL,
    MODELS,
)
from backend.parsers_and_generators.context_helpers import resolve_placeholders
from backend.parsers_and_generators.file_type_docx import DOCXf
from backend.parsers_and_generators.file_type_tex_j2 import J2f
from backend.parsers_and_generators.file_type_txt_j2 import TXTf
from backend.parsers_and_generators.page_count_docx import (
    analyze_mbps_from_docx,
    get_docx_page_info,
)
from backend.parsers_and_generators.page_info import get_pdf_page_info
from backend.parsers_and_generators.visual_lines import analyze_mbps

from ..models import (
    GenerateTemplateRequest,
    GenerateTemplateResponse,
    ModelsResponse,
    PageInfoResponse,
    RetryRequest,
    TailorRequest,
    TailorResponse,
)
from .. import session_store

router = APIRouter()

_MOD_DEG_MAP = {m.value: m for m in MOD_DEG}


# ── helpers ─────────────────────────────────────────────────────────


def _build_context(mod_fields: dict, sensitive_fields: dict) -> dict[str, str]:
    ctx: dict[str, str | None] = dict(sensitive_fields)
    ctx.update(mod_fields)
    ctx = resolve_placeholders(ctx)
    return {k: v for k, v in ctx.items() if v is not None}


def _handler_for(fmt: str, template_path: Path, out_dir: Path):
    if fmt == "docx":
        return DOCXf(template_path, out_dir)
    if fmt == "txt":
        return TXTf(template_path, out_dir)
    if fmt == "tex":
        return J2f(template_path, out_dir)
    raise ValueError(f"Unknown format: {fmt}")


def _handler_class(fmt: str):
    return {"docx": DOCXf, "txt": TXTf, "tex": J2f}[fmt]


def _split_placeholder_dicts(placeholders: dict) -> tuple[dict, dict]:
    """Return (tailor_fields, sensitive_fields) from the session placeholder map."""
    fields: dict[str, str] = {}
    sensitive: dict[str, str] = {}
    for key, ph in placeholders.items():
        if ph["type"] == "tailor":
            fields[key] = ph["selected_text"]
        elif ph["type"] == "sensitive":
            sensitive[key] = ph.get("value") or ph["selected_text"]
    return fields, sensitive


def _generate_preview(output_path: Path, file_format: str) -> str:
    if file_format == "docx":
        with open(output_path, "rb") as fh:
            result = mammoth.convert_to_html(fh)
        return result.value
    if file_format == "txt":
        with open(output_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return f'<pre style="white-space:pre-wrap;">{html_mod.escape(text)}</pre>'
    return '<p class="text-gray-400">PDF generated — use the download button.</p>'


def _check_pages(output_path: Path, fmt: str) -> Optional[dict]:
    is_tex = fmt == "tex"
    pi = get_pdf_page_info(output_path) if is_tex else get_docx_page_info(output_path)
    if pi is None:
        return None
    return {"page_count": pi["page_count"], "last_page_fill_pct": pi["last_page_fill_pct"]}


# ── offset-based template generation ───────────────────────────────


def _replace_in_docx_paragraph(para, local_start: int, local_end: int, token: str):
    """Replace characters [local_start:local_end] in a DOCX paragraph's runs."""
    runs = list(para.runs)
    if not runs:
        return

    cum = []
    pos = 0
    for run in runs:
        cum.append(pos)
        pos += len(run.text)

    first = last = None
    for i, run in enumerate(runs):
        rs = cum[i]
        re_ = rs + len(run.text)
        if rs < local_end and re_ > local_start:
            if first is None:
                first = i
            last = i

    if first is None:
        return

    first_run = runs[first]
    first_rs = cum[first]
    prefix = first_run.text[: local_start - first_rs]

    last_run = runs[last]
    last_rs = cum[last]
    suffix = last_run.text[local_end - last_rs :]

    if first == last:
        first_run.text = prefix + token + suffix
    else:
        first_run.text = prefix + token
        for i in range(first + 1, last):
            runs[i].text = ""
        last_run.text = suffix


def _generate_template_files(session_id: str, session: dict) -> None:
    fmt = session["file_format"]
    original = session_store.original_file_path(session_id)
    template = session_store.template_file_path(session_id)
    phs = session["placeholders"]

    sorted_phs = sorted(phs.values(), key=lambda p: p["start_offset"], reverse=True)

    if fmt in ("txt", "tex"):
        with open(original, "r", encoding="utf-8") as f:
            content = f.read()

        for ph in sorted_phs:
            if fmt == "tex":
                token = "((( " + ph["key"] + " )))"
            else:
                token = "{{ " + ph["key"] + " }}"
            content = (
                content[: ph["start_offset"]] + token + content[ph["end_offset"] :]
            )

        with open(template, "w", encoding="utf-8") as f:
            f.write(content)

    elif fmt == "docx":
        from docx import Document

        shutil.copy2(original, template)
        doc = Document(str(template))

        paragraphs = list(doc.paragraphs)
        para_offsets: list[tuple[int, int]] = []
        offset = 0
        for para in paragraphs:
            plen = len(para.text)
            para_offsets.append((offset, offset + plen))
            offset += plen + 1

        for ph in sorted_phs:
            s, e = ph["start_offset"], ph["end_offset"]
            token = "{{ " + ph["key"] + " }}"

            for pi, (ps, pe) in enumerate(para_offsets):
                if ps <= s < pe:
                    local_s = s - ps
                    local_e = min(e, pe) - ps
                    _replace_in_docx_paragraph(
                        paragraphs[pi], local_s, local_e, token
                    )
                    break

        doc.save(str(template))

    session_store.update_session(session_id, {"template_generated": True})


@router.post("/generate-template", response_model=GenerateTemplateResponse)
async def generate_template(body: GenerateTemplateRequest):
    try:
        session = session_store.get_session(body.session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if not session["placeholders"]:
        raise HTTPException(400, "No placeholders defined — mark regions first")

    _generate_template_files(body.session_id, session)
    template_path = session_store.template_file_path(body.session_id)
    preview: str | None = None
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            preview = f.read()[:4000]
    except Exception:
        pass

    return GenerateTemplateResponse(
        success=True,
        template_preview=preview,
        message="Template generated successfully",
    )


# ── tailor ──────────────────────────────────────────────────────────


@router.post("/tailor", response_model=TailorResponse)
async def tailor(req: TailorRequest):
    try:
        session = session_store.get_session(req.session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if not session["placeholders"]:
        raise HTTPException(400, "No placeholders defined")

    if not session["template_generated"]:
        _generate_template_files(req.session_id, session)
        session = session_store.get_session(req.session_id)

    fmt = session["file_format"]
    template_path = session_store.template_file_path(req.session_id)
    out_dir = session_store.output_dir(req.session_id)

    fields, sensitive_fields = _split_placeholder_dicts(session["placeholders"])
    handler = _handler_for(fmt, template_path, out_dir)
    handler_cls = _handler_class(fmt)
    full_resume = handler.get_resume_str()

    mod_deg = _MOD_DEG_MAP.get(req.moddeg, MOD_DEG.LOW)
    model = req.model or DEFAULT_MODEL
    if model not in MODELS:
        raise HTTPException(400, f"Unknown model: {model}")

    payload: LLM_I = {
        "full_resume": full_resume,
        "placeholders": fields,
        "mod_deg": mod_deg,
        "faux": req.faux,
        "job_posting": req.job_posting,
        "acc": req.acc,
    }

    baseline_fields: dict | None = None
    page_hint: int | None = None
    if req.pages and handler_cls in (DOCXf, J2f):
        page_hint = req.pages
        pre_ctx = _build_context(fields, sensitive_fields)
        tmp_dir = Path(tempfile.mkdtemp(prefix="resumate_pre_"))
        try:
            pre_ft = handler_cls(template_path, tmp_dir)
            pre_ft.post_llm_process(pre_ctx, metadata={"timestamp": int(time.time()), "suffix": "_pre"})
            baseline_fields = fields
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    llm_resp = CALL(payload, model=model, page_hint=page_hint, baseline_fields=baseline_fields)
    mod_fields = llm_resp["placeholders"]
    changes_made: str = llm_resp.get("changes_made", "")

    run_ts = int(time.time())
    output_id = uuid.uuid4().hex[:8]
    run_meta = {
        "model": model,
        "posting": "web",
        "moddeg": mod_deg.value,
        "faux": req.faux,
        "timestamp": run_ts,
    }

    clean_ctx = _build_context(mod_fields, sensitive_fields)
    output_path = handler.post_llm_process(clean_ctx, metadata=run_meta)

    page_info_resp: PageInfoResponse | None = None
    can_retry = False
    retry_number = 0

    if req.pages and handler_cls in (DOCXf, J2f):
        is_tex = handler_cls is J2f
        pi = _check_pages(output_path, fmt)

        if pi:
            within = pi["page_count"] <= req.pages
            page_info_resp = PageInfoResponse(
                page_count=pi["page_count"],
                last_page_fill_pct=pi["last_page_fill_pct"],
                target_pages=req.pages,
                within_target=within,
            )

            if not within:
                mbp = (
                    analyze_mbps(output_path, mod_fields)
                    if is_tex
                    else analyze_mbps_from_docx(output_path, mod_fields)
                )
                retry_payload: LLM_I = {**payload, "placeholders": mod_fields}
                retry_fn = CALL_RETRY_TEX if is_tex else CALL_RETRY
                retry_resp = retry_fn(
                    retry_payload,
                    actual_pages=pi["page_count"],
                    target_pages=req.pages,
                    last_page_fill_pct=pi["last_page_fill_pct"],
                    mbp_analysis=mbp,
                    model=model,
                )
                mod_fields = retry_resp["placeholders"]
                changes_made = retry_resp.get("changes_made", changes_made)
                clean_ctx = _build_context(mod_fields, sensitive_fields)

                handler2 = _handler_for(fmt, template_path, out_dir)
                output_path = handler2.post_llm_process(
                    clean_ctx, metadata={**run_meta, "suffix": "_retry"},
                )
                retry_number = 1

                pi2 = _check_pages(output_path, fmt)
                if pi2:
                    within2 = pi2["page_count"] <= req.pages
                    page_info_resp = PageInfoResponse(
                        page_count=pi2["page_count"],
                        last_page_fill_pct=pi2["last_page_fill_pct"],
                        target_pages=req.pages,
                        within_target=within2,
                    )
                    can_retry = not within2

    preview_html = _generate_preview(output_path, fmt)

    output_info = {
        "output_id": output_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(output_path),
        "mod_fields": mod_fields,
        "page_info": page_info_resp.model_dump() if page_info_resp else None,
        "retry_number": retry_number,
        "model": model,
        "moddeg": mod_deg.value,
        "faux": req.faux,
        "pages": req.pages,
        "job_posting": req.job_posting,
        "acc": req.acc,
    }
    session_store.add_output(req.session_id, output_info)

    return TailorResponse(
        output_id=output_id,
        preview_html=preview_html,
        download_url=f"/api/output/{req.session_id}/{output_id}/download",
        page_info=page_info_resp,
        can_retry=can_retry,
        retry_number=retry_number,
        changes_made=changes_made or None,
    )


# ── retry (user-initiated, indefinite) ─────────────────────────────


@router.post("/retry", response_model=TailorResponse)
async def retry(req: RetryRequest):
    try:
        session = session_store.get_session(req.session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    prev_output = session_store.get_output(req.session_id, req.output_id)
    if prev_output is None:
        raise HTTPException(404, "Output not found")

    pages = prev_output.get("pages")
    if not pages:
        raise HTTPException(400, "Cannot retry without a page target")

    fmt = session["file_format"]
    template_path = session_store.template_file_path(req.session_id)
    out_dir = session_store.output_dir(req.session_id)

    prev_mod_fields = prev_output["mod_fields"]
    model = prev_output["model"]
    mod_deg = _MOD_DEG_MAP.get(prev_output["moddeg"], MOD_DEG.LOW)
    faux = prev_output["faux"]
    job_posting = prev_output["job_posting"]
    acc = prev_output["acc"]

    _, sensitive_fields = _split_placeholder_dicts(session["placeholders"])

    handler = _handler_for(fmt, template_path, out_dir)
    full_resume = handler.get_resume_str()
    is_tex = fmt == "tex"

    prev_path = Path(prev_output["file_path"])
    mbp = (
        analyze_mbps(prev_path, prev_mod_fields)
        if is_tex
        else analyze_mbps_from_docx(prev_path, prev_mod_fields)
    )

    prev_pi = prev_output.get("page_info") or {}
    actual = prev_pi.get("page_count", 2)
    fill = prev_pi.get("last_page_fill_pct", 0.5)

    payload: LLM_I = {
        "full_resume": full_resume,
        "placeholders": prev_mod_fields,
        "mod_deg": mod_deg,
        "faux": faux,
        "job_posting": job_posting,
        "acc": acc,
    }

    retry_fn = CALL_RETRY2_TEX if is_tex else CALL_RETRY2
    llm_resp = retry_fn(
        payload,
        actual_pages=actual,
        target_pages=pages,
        last_page_fill_pct=fill,
        mbp_analysis=mbp,
        model=model,
    )

    new_mod = llm_resp["placeholders"]
    changes_made_retry: str = llm_resp.get("changes_made", "")
    retry_number = prev_output["retry_number"] + 1
    run_ts = int(time.time())
    output_id = uuid.uuid4().hex[:8]
    run_meta = {
        "model": model,
        "posting": "web",
        "moddeg": mod_deg.value,
        "faux": faux,
        "timestamp": run_ts,
        "suffix": f"_retry{retry_number}",
    }

    clean_ctx = _build_context(new_mod, sensitive_fields)
    handler2 = _handler_for(fmt, template_path, out_dir)
    output_path = handler2.post_llm_process(clean_ctx, metadata=run_meta)

    page_info_resp: PageInfoResponse | None = None
    can_retry = False
    pi = _check_pages(output_path, fmt)
    if pi:
        within = pi["page_count"] <= pages
        page_info_resp = PageInfoResponse(
            page_count=pi["page_count"],
            last_page_fill_pct=pi["last_page_fill_pct"],
            target_pages=pages,
            within_target=within,
        )
        can_retry = not within

    preview_html = _generate_preview(output_path, fmt)

    output_info = {
        "output_id": output_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(output_path),
        "mod_fields": new_mod,
        "page_info": page_info_resp.model_dump() if page_info_resp else None,
        "retry_number": retry_number,
        "model": model,
        "moddeg": mod_deg.value,
        "faux": faux,
        "pages": pages,
        "job_posting": job_posting,
        "acc": acc,
    }
    session_store.add_output(req.session_id, output_info)

    return TailorResponse(
        output_id=output_id,
        preview_html=preview_html,
        download_url=f"/api/output/{req.session_id}/{output_id}/download",
        page_info=page_info_resp,
        can_retry=can_retry,
        retry_number=retry_number,
        changes_made=changes_made_retry or None,
    )


# ── models list ─────────────────────────────────────────────────────


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    return ModelsResponse(models=list(MODELS.keys()), default_model=DEFAULT_MODEL)
