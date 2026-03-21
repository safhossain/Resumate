"""
DOCX-specific page analysis.  Converts .docx -> PDF via LibreOffice headless,
then delegates to the pure-PDF helpers in page_info.py for the actual analysis.

LibreOffice is the only free option that performs a real layout pass on DOCX
files -- page count and line breaks are emergent rendering properties that cannot
be read from the docx XML without a layout engine.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, TypedDict

from .page_info import (
    PageInfo, LineAnalysis, WIDOW_FILL_THRESHOLD,
    get_pdf_page_info, detect_widow_lines_from_pdf, analyze_lines,
)
from .visual_lines import MbpAnalysis, analyze_mbps


class DocxPageInfo(TypedDict):
    page_count: int
    last_page_fill_pct: float  # 0.0 - 1.0; fraction of last page occupied by content


def _find_libreoffice() -> Optional[str]:
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _libreoffice_to_pdf(docx_path: Path, lo: str, tmp_dir: str) -> Optional[Path]:
    """Run LibreOffice headless conversion; return PDF path or None on failure."""
    cmd = [
        lo,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", tmp_dir,
        str(docx_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except subprocess.CalledProcessError as e:
        print(f"WARNING: LibreOffice conversion failed (exit {e.returncode}).")
        return None
    except subprocess.TimeoutExpired:
        print("WARNING: LibreOffice conversion timed out.")
        return None

    pdf_path = Path(tmp_dir) / (docx_path.stem + ".pdf")
    if not pdf_path.exists():
        print("WARNING: LibreOffice did not produce a PDF.")
        return None
    return pdf_path


def get_docx_page_info(docx_path: Path) -> Optional[DocxPageInfo]:
    """
    Return page count and last-page fill fraction for *docx_path*, rendered via
    LibreOffice.

    Returns None (and prints a warning) if LibreOffice is unavailable, the
    conversion fails, or PyMuPDF cannot read the resulting PDF.
    """
    lo = _find_libreoffice()
    if lo is None:
        print("WARNING: LibreOffice not found on PATH — page info check skipped.")
        print("         Install LibreOffice and ensure 'libreoffice' or 'soffice' is on PATH.")
        return None

    docx_path = Path(docx_path).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _libreoffice_to_pdf(docx_path, lo, tmp_dir)
        if pdf_path is None:
            return None

        info = get_pdf_page_info(pdf_path)
        if info is None:
            return None
        return DocxPageInfo(page_count=info["page_count"],
                           last_page_fill_pct=info["last_page_fill_pct"])


def detect_widow_lines_from_docx(
    docx_path: Path,
    mod_fields: dict,
    fill_threshold: float = WIDOW_FILL_THRESHOLD,
) -> dict:
    """
    Convert *docx_path* to PDF via LibreOffice and detect widow-line paragraphs.

    Returns {placeholder_key: placeholder_value} for each detected widow, or {}
    if LibreOffice is unavailable, conversion fails, or no widows are found.
    """
    lo = _find_libreoffice()
    if lo is None:
        print("WARNING: LibreOffice not found — widow line detection skipped.")
        return {}

    docx_path = Path(docx_path).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _libreoffice_to_pdf(docx_path, lo, tmp_dir)
        if pdf_path is None:
            return {}

        try:
            return detect_widow_lines_from_pdf(pdf_path, mod_fields, fill_threshold)
        except Exception as e:
            print(f"WARNING: Widow line detection failed: {e}")
            return {}


def analyze_lines_from_docx(
    docx_path: Path,
    mod_fields: dict,
    fill_threshold: float = WIDOW_FILL_THRESHOLD,
) -> Optional[LineAnalysis]:
    """
    Convert *docx_path* to PDF via LibreOffice and run full line analysis.

    Returns a LineAnalysis dict, or None if LibreOffice is unavailable or
    conversion fails.
    """
    lo = _find_libreoffice()
    if lo is None:
        print("WARNING: LibreOffice not found — line analysis skipped.")
        return None

    docx_path = Path(docx_path).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _libreoffice_to_pdf(docx_path, lo, tmp_dir)
        if pdf_path is None:
            return None

        try:
            return analyze_lines(pdf_path, mod_fields, fill_threshold)
        except Exception as e:
            print(f"WARNING: Line analysis failed: {e}")
            return None


def analyze_mbps_from_docx(
    docx_path: Path,
    mod_fields: dict,
) -> Optional[MbpAnalysis]:
    """Convert *docx_path* to PDF via LibreOffice and run MBP analysis.

    Returns an MbpAnalysis, or None if LibreOffice is unavailable or
    conversion fails.
    """
    lo = _find_libreoffice()
    if lo is None:
        print("WARNING: LibreOffice not found — MBP analysis skipped.")
        return None

    docx_path = Path(docx_path).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _libreoffice_to_pdf(docx_path, lo, tmp_dir)
        if pdf_path is None:
            return None

        try:
            return analyze_mbps(pdf_path, mod_fields)
        except Exception as e:
            print(f"WARNING: MBP analysis failed: {e}")
            return None
