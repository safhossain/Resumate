"""
Pure-PDF page analysis using PyMuPDF.  No external layout engines required —
the caller is expected to supply an already-rendered PDF path.

Provides:
  - get_pdf_page_info       : page count + last-page fill percentage
  - analyze_lines           : rich widow-line detection with per-line metrics
  - detect_widow_lines_from_pdf : backward-compat thin wrapper (returns {key: value})
"""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, TypedDict

# Last line of a multi-line block is considered a "widow" if its width is
# below this fraction of the page's reference line width
WIDOW_FILL_THRESHOLD: float = 0.25


class PageInfo(TypedDict):
    page_count: int
    last_page_fill_pct: float  # 0.0 – 1.0; fraction of last page occupied by content


class WidowDetail(TypedDict):
    key: str
    value: str
    fill_ratio: float       # how full the widow line is (0.0-1.0)
    widow_line_chars: int   # char count of the trailing widow line text
    chars_to_cut: int       # approx chars to remove to eliminate the widow


class LineAnalysis(TypedDict):
    widows: dict                         # {key: value} — backward-compat
    widow_details: list[WidowDetail]
    avg_filled_line_chars_bullet: float
    avg_filled_line_chars_para: float
    avg_widow_line_chars: float
    total_filled_lines: int
    total_widow_lines: int


_BULLET_STRIP_RE = re.compile(
    r'^[\s\u2022\u2023\u25e6\u2043\u2219\u25cf\u25aa\u25ab\-\*\•●▪›◦⁃]+\s*'
)


def _norm(text: str) -> str:
    """Collapse whitespace and lowercase for fuzzy matching."""
    return " ".join(text.lower().split())


def _line_spans_text(line: dict) -> str:
    """Return all text from a single line, joined across spans."""
    return " ".join(span.get("text", "") for span in line.get("spans", [])).strip()


def _block_spans_text(block: dict) -> str:
    """Return all text from a block, joined across lines and spans."""
    return " ".join(
        _line_spans_text(line) for line in block.get("lines", [])
    ).strip()


def _strip_bullets(text: str) -> str:
    """Remove leading bullet/list characters so plain text remains for matching."""
    return _BULLET_STRIP_RE.sub("", text).strip()


def _is_bullet_block(block: dict) -> bool:
    """Heuristic: block is a bullet if its first line starts with a bullet char."""
    lines = block.get("lines", [])
    if not lines:
        return False
    first_text = _line_spans_text(lines[0])
    return bool(_BULLET_STRIP_RE.match(first_text))


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


def analyze_lines(
    pdf_path: Path,
    mod_fields: dict,
    fill_threshold: float = WIDOW_FILL_THRESHOLD,
) -> LineAnalysis:
    """
    Scan *pdf_path* for widow lines and compute per-line character metrics.

    Returns a LineAnalysis dict with:
      - widows: {key: value} backward-compat mapping
      - widow_details: per-widow rich info (fill ratio, chars, chars_to_cut)
      - avg char counts for filled lines (bullet vs para) and widow lines
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))

    # Accumulators for line metrics
    filled_chars_bullet: list[int] = []
    filled_chars_para: list[int] = []
    widow_chars_all: list[int] = []

    # Raw widow candidates: (block_text_for_matching, widow_line_chars, fill_ratio)
    _WidowRaw = tuple[str, int, float]
    widow_candidates: list[_WidowRaw] = []

    for page in doc:
        page_dict = page.get_text("dict")
        text_blocks = [
            b for b in page_dict.get("blocks", []) if b.get("type", 0) == 0
        ]
        if not text_blocks:
            continue

        # 75th-percentile reference width (avoids distortion from indentation)
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

            is_bullet = _is_bullet_block(block)

            # Collect char counts for every line in this block
            for l_idx, line in enumerate(lines):
                lx0, _, lx1, _ = line["bbox"]
                lw = lx1 - lx0
                if lw < 20:
                    continue

                line_text = _line_spans_text(line)
                line_chars = len(line_text)
                line_fill = lw / ref_width

                is_last = (l_idx == len(lines) - 1)

                if is_last and line_fill < fill_threshold and len(lines) >= 2:
                    # This is a widow line of a multi-line block
                    widow_chars_all.append(line_chars)
                elif line_fill >= fill_threshold:
                    # "Filled" line
                    if is_bullet:
                        filled_chars_bullet.append(line_chars)
                    else:
                        filled_chars_para.append(line_chars)

            # --- Widow candidate detection (for placeholder matching) ---
            last_line = lines[-1]
            ll_x0, _, ll_x1, _ = last_line["bbox"]
            last_line_width = ll_x1 - ll_x0

            if last_line_width < 20:
                continue

            fill_ratio = last_line_width / ref_width
            if fill_ratio >= fill_threshold:
                continue

            is_widow = False
            if len(lines) >= 2:
                is_widow = True
            elif b_idx > 0:
                prev_block = text_blocks[b_idx - 1]
                prev_lines = prev_block.get("lines", [])
                if prev_lines:
                    pl_x0, _, pl_x1, _ = prev_lines[-1]["bbox"]
                    prev_fill = (pl_x1 - pl_x0) / ref_width
                    if prev_fill >= fill_threshold:
                        is_widow = True

            if not is_widow:
                continue

            widow_line_text = _line_spans_text(last_line)
            widow_line_chars = len(widow_line_text)

            # For single-line continuation blocks, also account in widow_chars
            if len(lines) == 1:
                widow_chars_all.append(widow_line_chars)

            # Build text for fuzzy matching
            raw_text = _block_spans_text(block)
            if len(lines) == 1 and b_idx > 0:
                prev_raw = _block_spans_text(text_blocks[b_idx - 1])
                raw_text = f"{prev_raw} {raw_text}"

            clean_text = _strip_bullets(raw_text)
            if clean_text:
                widow_candidates.append((clean_text, widow_line_chars, fill_ratio))

    doc.close()

    # --- Fuzzy-match widow candidates to placeholder keys ---
    widows: dict = {}
    widow_details: list[WidowDetail] = []
    used_keys: set = set()
    match_threshold = 0.55

    for block_text, wl_chars, w_fill in widow_candidates:
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
            widow_details.append(WidowDetail(
                key=best_key,
                value=mod_fields[best_key],
                fill_ratio=w_fill,
                widow_line_chars=wl_chars,
                chars_to_cut=wl_chars,
            ))

    # --- Compute averages ---
    avg_bullet = (sum(filled_chars_bullet) / len(filled_chars_bullet)) if filled_chars_bullet else 0.0
    avg_para = (sum(filled_chars_para) / len(filled_chars_para)) if filled_chars_para else 0.0
    avg_widow = (sum(widow_chars_all) / len(widow_chars_all)) if widow_chars_all else 0.0

    return LineAnalysis(
        widows=widows,
        widow_details=widow_details,
        avg_filled_line_chars_bullet=round(avg_bullet, 1),
        avg_filled_line_chars_para=round(avg_para, 1),
        avg_widow_line_chars=round(avg_widow, 1),
        total_filled_lines=len(filled_chars_bullet) + len(filled_chars_para),
        total_widow_lines=len(widow_chars_all),
    )


def detect_widow_lines_from_pdf(
    pdf_path: Path,
    mod_fields: dict,
    fill_threshold: float = WIDOW_FILL_THRESHOLD,
) -> dict:
    """Backward-compat wrapper: returns {placeholder_key: value} for each widow."""
    result = analyze_lines(pdf_path, mod_fields, fill_threshold)
    return result["widows"]
