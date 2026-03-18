"""
Convert a .docx to PDF using LibreOffice headless, then use PyMuPDF to:
  - return page count and last-page fill percentage (get_docx_page_info)
  - detect "widow line" paragraphs — multi-line blocks whose final line is
    only partially filled (detect_widow_lines_from_docx)

Fill percentage = (lowest Y coordinate of any content block on the last page)
                  / (total page height)

Widow line detection: for each multi-line text block, if the last line's width
is less than `fill_threshold` fraction of the block's full width, it is a widow
candidate. These blocks are fuzzy-matched back to placeholder keys so the LLM
can be told exactly which values to rephrase for a 1-line reduction.

LibreOffice is the only free option that performs a real layout pass on DOCX
files — page count and line breaks are emergent rendering properties that cannot
be read from the docx XML without a layout engine.
"""

import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, TypedDict


class DocxPageInfo(TypedDict):
    page_count: int
    last_page_fill_pct: float  # 0.0 – 1.0; fraction of last page occupied by content


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


_BULLET_STRIP_RE = re.compile(
    r'^[\s\u2022\u2023\u25e6\u2043\u2219\u25cf\u25aa\u25ab\-\*\•●▪›◦⁃]+\s*'
)


def _norm(text: str) -> str:
    """Collapse whitespace and lowercase for fuzzy matching."""
    return " ".join(text.lower().split())


def _block_spans_text(block: dict) -> str:
    """Return all text from a block, joined across lines and spans."""
    return " ".join(
        " ".join(span.get("text", "") for span in line.get("spans", []))
        for line in block.get("lines", [])
    ).strip()


def _strip_bullets(text: str) -> str:
    """Remove leading bullet/list characters so plain text remains for matching."""
    return _BULLET_STRIP_RE.sub("", text).strip()


def _detect_widow_lines_from_pdf(
    pdf_path: Path,
    mod_fields: dict,
    fill_threshold: float = 0.50,
) -> dict:
    """
    Scan *pdf_path* for widow lines — rendered lines that are the last (short)
    line of a paragraph — and match them back to placeholder keys.

    Two scenarios are handled:
    1. Multi-line block: the block has >=2 lines and the last line is short.
    2. Split continuation block: LibreOffice / PyMuPDF sometimes puts the
       continuation of a wrapped paragraph into a separate single-line block.
       Detected by: this block is narrow AND the immediately preceding block's
       last line is wide.

    Uses the 75th-percentile line width on each page as the reference width so
    bullet indentation and block-level x offsets don't distort the ratio.

    Returns {placeholder_key: placeholder_value} for each matched widow.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    widow_candidates: list[str] = []

    for page in doc:
        page_dict = page.get_text("dict")
        text_blocks = [
            b for b in page_dict.get("blocks", []) if b.get("type", 0) == 0
        ]
        if not text_blocks:
            continue

        # Compute a page-level reference width (75th percentile of all line
        # widths > 20 px) so we're not fooled by block-level x offsets from
        # list indentation or hanging bullets.
        all_widths: list[float] = []
        for block in text_blocks:
            for line in block.get("lines", []):
                x0, _, x1, _ = line["bbox"]
                w = x1 - x0
                if w > 20:
                    all_widths.append(w)
        if not all_widths:
            continue
        all_widths.sort()
        ref_width: float = all_widths[int(len(all_widths) * 0.75)]
        if ref_width <= 0:
            continue

        for b_idx, block in enumerate(text_blocks):
            lines = block.get("lines", [])
            if not lines:
                continue

            last_line = lines[-1]
            ll_x0, _, ll_x1, _ = last_line["bbox"]
            last_line_width = ll_x1 - ll_x0

            # Skip decorative/symbol-only elements (very narrow)
            if last_line_width < 20:
                continue

            fill_ratio = last_line_width / ref_width
            if fill_ratio >= fill_threshold:
                continue  # last line is wide — not a widow

            is_widow = False
            if len(lines) >= 2:
                # Multi-line block: short last line is a classic widow.
                is_widow = True
            elif b_idx > 0:
                # Single-line block: widow only if the preceding block's last
                # line was wide (indicating the text flowed from that block).
                prev_block = text_blocks[b_idx - 1]
                prev_lines = prev_block.get("lines", [])
                if prev_lines:
                    pl_x0, _, pl_x1, _ = prev_lines[-1]["bbox"]
                    prev_fill = (pl_x1 - pl_x0) / ref_width
                    if prev_fill >= fill_threshold:
                        is_widow = True

            if not is_widow:
                continue

            # Build the text to match.  For single-line continuation blocks,
            # prepend the preceding block's text so there's enough content for
            # a reliable fuzzy match against the full placeholder value.
            raw_text = _block_spans_text(block)
            if len(lines) == 1 and is_widow and b_idx > 0:
                prev_raw = _block_spans_text(text_blocks[b_idx - 1])
                raw_text = f"{prev_raw} {raw_text}"

            clean_text = _strip_bullets(raw_text)
            if clean_text:
                widow_candidates.append(clean_text)

    doc.close()

    # Fuzzy-match each candidate to the best-fitting placeholder key.
    widows: dict = {}
    used_keys: set = set()
    match_threshold = 0.55  # slightly lenient to survive minor bullet/format diffs

    for block_text in widow_candidates:
        norm_block = _norm(block_text)
        best_key: Optional[str] = None
        best_ratio = match_threshold

        for key, value in mod_fields.items():
            if key in used_keys:
                continue
            if value.strip() == "REMOVE_BULLETPOINT":
                continue
            ratio = SequenceMatcher(None, norm_block, _norm(value)).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key

        if best_key is not None:
            widows[best_key] = mod_fields[best_key]
            used_keys.add(best_key)

    return widows


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

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            page_count: int = doc.page_count

            last_page = doc[-1]
            page_height: float = last_page.rect.height

            # get_text("blocks") → list of (x0, y0, x1, y1, text, block_no, block_type)
            # Use y1 of the lowest block to measure fill.
            blocks = last_page.get_text("blocks")
            if blocks and page_height > 0:
                max_y = max(b[3] for b in blocks)
                fill_pct = min(max_y / page_height, 1.0)
            else:
                fill_pct = 0.0

            doc.close()
            return DocxPageInfo(page_count=page_count, last_page_fill_pct=fill_pct)

        except Exception as e:
            print(f"WARNING: Could not read PDF page info: {e}")
            return None


def detect_widow_lines_from_docx(
    docx_path: Path,
    mod_fields: dict,
    fill_threshold: float = 0.50,
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
            return _detect_widow_lines_from_pdf(pdf_path, mod_fields, fill_threshold)
        except Exception as e:
            print(f"WARNING: Widow line detection failed: {e}")
            return {}
