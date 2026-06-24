"""
Pure-PDF page analysis using PyMuPDF.  No external layout engines required —
the caller is expected to supply an already-rendered PDF path.

Provides:
  - get_pdf_page_info : page count + last-page fill percentage

Rich widow/line analysis was superseded by the visual-line approach in
``visual_lines.analyze_mbps`` and has been removed.
"""

from pathlib import Path
from typing import Optional, TypedDict


class PageInfo(TypedDict):
    page_count: int
    last_page_fill_pct: float  # 0.0 – 1.0; fraction of last page occupied by content


def get_pdf_page_info(pdf_path: Path) -> Optional[PageInfo]:
    """
    Return page count and last-page fill fraction for *pdf_path*.

    Returns None (and prints a warning) if PyMuPDF cannot read the PDF.
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        page_count: int = doc.page_count

        last_page = doc[-1]
        page_height: float = last_page.rect.height

        blocks = last_page.get_text("blocks")
        if blocks and page_height > 0:
            max_y = max(b[3] for b in blocks)
            fill_pct = min(max_y / page_height, 1.0)
        else:
            fill_pct = 0.0

        doc.close()
        return PageInfo(page_count=page_count, last_page_fill_pct=fill_pct)

    except Exception as e:
        print(f"WARNING: Could not read PDF page info: {e}")
        return None
