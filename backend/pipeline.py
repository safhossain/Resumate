"""Shared tailoring-pipeline helpers used by both the CLI (``backend/main.py``)
and the webapp routers (``backend/api/routers/tailor.py``).

These centralize the format-dependent branching (DOCX vs LaTeX) and the
context/metadata construction that previously lived, duplicated, in both
entry points. The CLI keeps its console printing/prompting and the router
keeps its HTTP/session plumbing; only the shared core lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .llm_integration.LLM_CALL import (
    CALL_RETRY,
    CALL_RETRY2,
    CALL_RETRY_TEX,
    CALL_RETRY2_TEX,
)
from .parsers_and_generators.context_helpers import resolve_placeholders
from .parsers_and_generators.file_type_docx import DOCXf
from .parsers_and_generators.file_type_tex_j2 import J2f
from .parsers_and_generators.page_count_docx import (
    analyze_mbps_from_docx,
    get_docx_page_info,
)
from .parsers_and_generators.page_info import get_pdf_page_info
from .parsers_and_generators.visual_lines import analyze_mbps

# Handler classes that participate in the ``--pages`` page-limit pipeline.
PAGE_LIMIT_HANDLERS = (DOCXf, J2f)


def build_context(placeholder_values: dict, sensitive_fields: dict) -> dict:
    """Merge sensitive fields + placeholder values, resolve nested
    ``{{ key }}`` references, and drop any ``None`` values."""
    ctx: dict = dict(sensitive_fields)
    ctx.update(placeholder_values)
    ctx = resolve_placeholders(ctx)
    return {k: v for k, v in ctx.items() if v is not None}


def build_run_meta(*, model, posting: str, mod_deg_value: str, faux: bool, timestamp: int) -> dict:
    """Construct the output-tagging metadata shared by every render of a run."""
    return {
        "model": model,
        "posting": posting,
        "moddeg": mod_deg_value,
        "faux": faux,
        "timestamp": timestamp,
    }


def is_tex_handler(handler_or_class) -> bool:
    """True if *handler_or_class* (a FileType instance or class) is the LaTeX handler."""
    cls = handler_or_class if isinstance(handler_or_class, type) else type(handler_or_class)
    return issubclass(cls, J2f)


def page_info_for(handler_or_class, output_path: Path) -> Optional[dict]:
    """Return page info for *output_path*, choosing the PDF or DOCX analyzer.

    LaTeX output is already a PDF (read directly via PyMuPDF); DOCX needs a
    LibreOffice → PDF conversion first.
    """
    if is_tex_handler(handler_or_class):
        return get_pdf_page_info(output_path)
    return get_docx_page_info(output_path)


def analyze_for(handler_or_class, output_path: Path, fields: dict):
    """Run MBP analysis on *output_path*, choosing the PDF or DOCX path."""
    if is_tex_handler(handler_or_class):
        return analyze_mbps(output_path, fields)
    return analyze_mbps_from_docx(output_path, fields)


def first_retry_fn(handler_or_class):
    """Return the first page-limit retry function for the handler's format."""
    return CALL_RETRY_TEX if is_tex_handler(handler_or_class) else CALL_RETRY


def second_retry_fn(handler_or_class):
    """Return the second (MBP-targeted) retry function for the handler's format."""
    return CALL_RETRY2_TEX if is_tex_handler(handler_or_class) else CALL_RETRY2
