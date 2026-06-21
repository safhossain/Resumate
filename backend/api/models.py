from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class DocumentElement(BaseModel):
    id: str
    type: str  # "paragraph" | "line"
    text: str
    offset: int  # character offset in raw_text


class UploadResponse(BaseModel):
    session_id: str
    rendered_html: str
    raw_text: str
    document_structure: list[DocumentElement]
    file_format: str  # "docx" | "txt" | "tex"
    tex_pdf_url: Optional[str] = None


class PlaceholderCreate(BaseModel):
    session_id: str
    selected_text: str
    start_offset: int
    end_offset: int
    key: Optional[str] = None
    type: str  # "tailor" | "sensitive"
    value: Optional[str] = None


class PlaceholderResize(BaseModel):
    start_offset: int
    end_offset: int


class PlaceholderResponse(BaseModel):
    key: str
    type: str
    selected_text: str
    start_offset: int
    end_offset: int
    value: Optional[str] = None
    warning: Optional[str] = None  # non-blocking advisory (e.g. brace imbalance in .tex)


class GenerateTemplateRequest(BaseModel):
    session_id: str


class GenerateTemplateResponse(BaseModel):
    success: bool
    template_preview: Optional[str] = None
    message: str


class TailorRequest(BaseModel):
    session_id: str
    job_posting: str
    acc: str = ""
    model: Optional[str] = None
    moddeg: str = "low"
    faux: bool = False
    pages: Optional[int] = None


class PageInfoResponse(BaseModel):
    page_count: int
    last_page_fill_pct: float
    target_pages: Optional[int] = None
    within_target: bool


class ChangeLogEntry(BaseModel):
    """A single LLM call's contribution to the running summary of changes."""
    stage: str               # "initial" | "auto_retry" | "manual_retry"
    label: str               # human-friendly stage description
    text: str                # raw changes_made string from the LLM
    page_count: Optional[int] = None
    target_pages: Optional[int] = None


class StageDownload(BaseModel):
    """Download links for a single pipeline stage output."""
    stage: str               # "initial" | "auto_retry" | "manual_retry"
    label: str               # human-readable, e.g. "Stage 1 — Initial"
    pdf_url: Optional[str] = None   # always set unless render failed
    tex_url: Optional[str] = None   # set for .tex outputs only


class FieldDiff(BaseModel):
    """A single placeholder whose value changed between two stages."""
    key: str
    old: str                 # value on the base side (the "-" lines)
    new: str                 # value on the compared side (the "+" lines)
    change_type: str         # "added" | "removed" | "modified"


class StageDiff(BaseModel):
    """Per-stage +/- comparison against the original and the previous stage.

    A "stage" is one rendered snapshot in the chain
    original → initial → auto_retry → manual_retry(s).
    The original is never itself a StageDiff; it is only a comparison base.
    """
    stage: str               # "initial" | "auto_retry" | "manual_retry"
    label: str               # human-friendly stage description
    stage_index: int         # 1-based position among non-original stages
    vs_original: list[FieldDiff] = []
    vs_previous: list[FieldDiff] = []
    # Label describing what "previous" is for this stage (e.g. "Original",
    # "Initial tailoring") so the UI can clarify the toggle.
    previous_label: str = "Original"


class TailorResponse(BaseModel):
    output_id: str
    preview_html: str
    download_url: str  # kept for backwards-compat — points to final/latest output
    page_info: Optional[PageInfoResponse] = None
    can_retry: bool = False
    retry_number: int = 0
    changes_made: Optional[str] = None  # most recent stage text (legacy)
    changes_log: list[ChangeLogEntry] = []
    render_error: Optional[str] = None
    stage_downloads: list[StageDownload] = []  # per-stage download links
    stage_diffs: list[StageDiff] = []  # per-stage +/- field comparisons


class RetryRequest(BaseModel):
    session_id: str
    output_id: str


class SessionSummary(BaseModel):
    session_id: str
    name: Optional[str]
    file_format: str
    original_filename: str
    placeholder_count: int
    created_at: str
    updated_at: str


class SessionDetail(BaseModel):
    session_id: str
    name: Optional[str]
    file_format: str
    original_filename: str
    created_at: str
    updated_at: str
    rendered_html: str
    raw_text: str
    document_structure: list[DocumentElement]
    placeholders: dict
    template_generated: bool
    outputs: list
    tex_pdf_url: Optional[str] = None
    acc: str = ""


class SessionSaveRequest(BaseModel):
    name: Optional[str] = None


class ModelsResponse(BaseModel):
    models: list[str]
    default_model: str
