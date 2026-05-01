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


class PlaceholderResponse(BaseModel):
    key: str
    type: str
    selected_text: str
    start_offset: int
    end_offset: int
    value: Optional[str] = None


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


class TailorResponse(BaseModel):
    output_id: str
    preview_html: str
    download_url: str
    page_info: Optional[PageInfoResponse] = None
    can_retry: bool = False
    retry_number: int = 0
    changes_made: Optional[str] = None


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
