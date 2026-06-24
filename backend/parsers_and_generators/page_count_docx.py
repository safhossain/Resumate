"""
DOCX-specific page analysis.  Converts .docx -> PDF via LibreOffice headless,
then delegates to the pure-PDF helpers for the actual analysis.

LibreOffice is the only free option that performs a real layout pass on DOCX
files -- page count and line breaks are emergent rendering properties that cannot
be read from the docx XML without a layout engine.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional, TypeVar, TypedDict

from .page_info import get_pdf_page_info
from .visual_lines import MbpAnalysis, analyze_mbps

T = TypeVar("T")


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


def _with_libreoffice_pdf(
    docx_path: Path,
    fn: Callable[[Path], T],
    *,
    purpose: str,
    default: T,
) -> T:
    """Convert *docx_path* to PDF via LibreOffice and run *fn* on the result.

    Centralizes the find-libreoffice -> temp-dir -> convert -> delegate pattern.
    Returns *default* (and prints a warning) if LibreOffice is unavailable or the
    conversion/analysis fails.
    """
    lo = _find_libreoffice()
    if lo is None:
        print(f"WARNING: LibreOffice not found on PATH — {purpose} skipped.")
        print("         Install LibreOffice and ensure 'libreoffice' or 'soffice' is on PATH.")
        return default

    docx_path = Path(docx_path).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _libreoffice_to_pdf(docx_path, lo, tmp_dir)
        if pdf_path is None:
            return default
        try:
            return fn(pdf_path)
        except Exception as e:
            print(f"WARNING: {purpose} failed: {e}")
            return default


def get_docx_page_info(docx_path: Path) -> Optional[DocxPageInfo]:
    """
    Return page count and last-page fill fraction for *docx_path*, rendered via
    LibreOffice.

    Returns None (and prints a warning) if LibreOffice is unavailable, the
    conversion fails, or PyMuPDF cannot read the resulting PDF.
    """
    def _analyze(pdf_path: Path) -> Optional[DocxPageInfo]:
        info = get_pdf_page_info(pdf_path)
        if info is None:
            return None
        return DocxPageInfo(
            page_count=info["page_count"],
            last_page_fill_pct=info["last_page_fill_pct"],
        )

    return _with_libreoffice_pdf(
        docx_path, _analyze, purpose="page info check", default=None
    )


def analyze_mbps_from_docx(
    docx_path: Path,
    mod_fields: dict,
) -> Optional[MbpAnalysis]:
    """Convert *docx_path* to PDF via LibreOffice and run MBP analysis.

    Returns an MbpAnalysis, or None if LibreOffice is unavailable or
    conversion fails.
    """
    return _with_libreoffice_pdf(
        docx_path,
        lambda pdf_path: analyze_mbps(pdf_path, mod_fields),
        purpose="MBP analysis",
        default=None,
    )
