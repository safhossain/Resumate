"""
Visual-line detection for PDF pages using PyMuPDF.

PyMuPDF's block → line → span hierarchy does NOT correspond to visual lines
as rendered.  This module rebuilds visual lines from raw span Y-coordinates,
then groups them into logical elements (bullets, paragraphs, headings).

Terminology:
  - Visual line: a horizontal row of text as seen by a human reader, defined
    by Y-coordinate clustering across ALL spans on the page.
  - MBP (Multi-line Bullet/Paragraph): a logical text element that wraps to
    2+ visual lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from ..constants import REMOVE_SENTINEL

_BULLET_CHARS = set("•●▪›◦⁃–-")
_BULLET_RE = re.compile(
    r'^[\s\u2022\u2023\u25e6\u2043\u2219\u25cf\u25aa\u25ab\-\*\•●▪›◦⁃]+\s'
)
Y_CLUSTER_TOLERANCE = 3.0  # pts — spans within this Y range are same visual line


@dataclass
class VisualLine:
    """One horizontal row of text as it appears on the page."""
    y_mid: float
    x_min: float
    x_max: float
    text: str
    char_count: int
    page_num: int  # 1-based


@dataclass
class LogicalElement:
    """A group of consecutive visual lines forming one semantic unit."""
    kind: str  # "bullet", "paragraph", "heading", "other"
    lines: list[VisualLine] = field(default_factory=list)
    page_num: int = 0

    @property
    def is_mbp(self) -> bool:
        return len(self.lines) >= 2

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def full_text(self) -> str:
        return " ".join(ln.text for ln in self.lines)

    @property
    def last_line(self) -> VisualLine | None:
        return self.lines[-1] if self.lines else None


def extract_visual_lines(pdf_path: Path, page_num: int | None = None) -> list[VisualLine]:
    """
    Extract visual lines from a PDF by clustering all text spans by Y-coordinate.

    Returns visual lines sorted by (page, y_mid, x_min).
    If *page_num* is given (1-based), only that page is processed.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    pages = [page_num - 1] if page_num else range(doc.page_count)
    all_lines: list[VisualLine] = []

    for pi in pages:
        page = doc[pi]
        page_dict = page.get_text("dict")

        # Collect every span with its bbox
        spans: list[dict] = []
        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    sx0, sy0, sx1, sy1 = bbox
                    spans.append({
                        "x0": sx0, "y0": sy0, "x1": sx1, "y1": sy1,
                        "y_mid": (sy0 + sy1) / 2,
                        "text": text,
                    })

        if not spans:
            continue

        # Sort by y_mid then x0
        spans.sort(key=lambda s: (s["y_mid"], s["x0"]))

        # Cluster by Y-coordinate
        clusters: list[list[dict]] = []
        current_cluster: list[dict] = [spans[0]]

        for sp in spans[1:]:
            if abs(sp["y_mid"] - current_cluster[-1]["y_mid"]) <= Y_CLUSTER_TOLERANCE:
                current_cluster.append(sp)
            else:
                clusters.append(current_cluster)
                current_cluster = [sp]
        clusters.append(current_cluster)

        # Build VisualLine from each cluster
        for cluster in clusters:
            cluster.sort(key=lambda s: s["x0"])
            x_min = min(s["x0"] for s in cluster)
            x_max = max(s["x1"] for s in cluster)
            y_mid = sum(s["y_mid"] for s in cluster) / len(cluster)
            text = " ".join(s["text"] for s in cluster).strip()
            # Remove double-spaces from span joining
            while "  " in text:
                text = text.replace("  ", " ")

            all_lines.append(VisualLine(
                y_mid=y_mid,
                x_min=x_min,
                x_max=x_max,
                text=text,
                char_count=len(text),
                page_num=pi + 1,
            ))

    doc.close()
    return all_lines


def _is_bullet_start(text: str) -> bool:
    """Check if text starts with a bullet character."""
    stripped = text.lstrip()
    if not stripped:
        return False
    return stripped[0] in _BULLET_CHARS or bool(_BULLET_RE.match(text))


def group_into_elements(
    visual_lines: list[VisualLine],
    page_width: float,
    margin_tolerance: float = 5.0,
) -> list[LogicalElement]:
    """
    Group consecutive visual lines into logical elements.

    Heuristics:
    - A line starting with a bullet char (•, -, etc.) begins a new bullet element.
    - Continuation lines of a bullet are expected at x_min close to the second
      line's indent (bullet text hangs right of the marker), typically ~9pt right
      of the bullet char x.
    - A line with a significantly different left margin or a large Y-gap starts
      a new element.
    - Short non-bullet lines are labeled "heading".
    """
    if not visual_lines:
        return []

    elements: list[LogicalElement] = []
    current: LogicalElement | None = None
    # For bullet elements: the x_min of the first continuation line (text indent)
    # is the reference for subsequent continuation lines.
    bullet_continuation_x: float | None = None

    for i, vl in enumerate(visual_lines):
        is_bullet = _is_bullet_start(vl.text)

        start_new = False

        if current is None:
            start_new = True
        elif is_bullet:
            start_new = True
        elif vl.page_num != current.page_num:
            start_new = True
        else:
            prev_line = current.lines[-1]
            y_gap = vl.y_mid - prev_line.y_mid

            if y_gap > 18.0:
                start_new = True
            elif current.kind == "bullet":
                # Bullet continuation: this line should have x_min close to
                # the continuation indent (typically ~9pt right of bullet x).
                if bullet_continuation_x is not None:
                    if abs(vl.x_min - bullet_continuation_x) > margin_tolerance:
                        start_new = True
                else:
                    # First continuation line after the bullet-start line.
                    # Accept if it's to the right of (or very close to) the bullet x.
                    bullet_x = current.lines[0].x_min
                    if vl.x_min < bullet_x - margin_tolerance:
                        start_new = True
                    # else: this is the first continuation, we'll record its x below
            else:
                ref_x = current.lines[0].x_min
                if abs(vl.x_min - ref_x) > margin_tolerance and \
                   abs(vl.x_min - prev_line.x_min) > margin_tolerance:
                    start_new = True

        if start_new:
            if current is not None:
                elements.append(current)

            kind = "bullet" if is_bullet else "paragraph"
            if not is_bullet and vl.char_count < 25 and (vl.x_max - vl.x_min) < page_width * 0.3:
                kind = "heading"

            current = LogicalElement(kind=kind, lines=[vl], page_num=vl.page_num)
            bullet_continuation_x = None
        else:
            assert current is not None
            current.lines.append(vl)
            # Record the continuation indent from the first wrap line of a bullet
            if current.kind == "bullet" and bullet_continuation_x is None and len(current.lines) == 2:
                bullet_continuation_x = vl.x_min

    if current is not None:
        elements.append(current)

    return elements


# ---------------------------------------------------------------------------
# MBP analysis — tier classification + fuzzy match to placeholder keys
# ---------------------------------------------------------------------------

TIER_A_THRESHOLD = 0.25   # last-line fill below this → easy win
TIER_B_THRESHOLD = 0.55   # last-line fill below this → moderate effort
BULLET_OVERHEAD = 8       # chars eaten by bullet marker + indent in rendered output

_STRIP_BULLETS_RE = re.compile(
    r'^[\s\u2022\u2023\u25e6\u2043\u2219\u25cf\u25aa\u25ab\-\*\•●▪›◦⁃]+\s*'
)

# Keys whose rendered text includes template content (dates, labels, etc.)
# that the LLM cannot control — skip these from MBP targeting.
_SKIP_KEY_SUFFIXES = ("_name", "_role", "_url", "_tech")


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


@dataclass
class MbpDetail:
    key: str
    value: str
    kind: str                 # "bullet" | "paragraph"
    visual_line_count: int
    last_line_fill: float     # 0.0–1.0
    last_line_chars: int
    last_line_text: str       # actual rendered text of the last visual line
    total_chars: int          # len(value) — full placeholder length
    one_line_cap: int         # max chars that fit on 1 rendered line for this kind
    chars_over: int           # total_chars - one_line_cap (clamped ≥ 0)
    tier: str                 # "A" | "B" | "C"


@dataclass
class MbpAnalysis:
    mbp_details: list[MbpDetail]
    avg_chars_per_bullet_line: float
    avg_chars_per_para_line: float
    total_visual_lines: int
    lines_on_last_page: int
    ref_width: float

    @property
    def tier_a(self) -> list[MbpDetail]:
        return [d for d in self.mbp_details if d.tier == "A"]

    @property
    def tier_b(self) -> list[MbpDetail]:
        return [d for d in self.mbp_details if d.tier == "B"]

    @property
    def tier_c(self) -> list[MbpDetail]:
        return [d for d in self.mbp_details if d.tier == "C"]


def analyze_mbps(
    pdf_path: Path,
    mod_fields: dict,
    tier_a_thresh: float = TIER_A_THRESHOLD,
    tier_b_thresh: float = TIER_B_THRESHOLD,
) -> MbpAnalysis:
    """Run visual-line analysis on *pdf_path* and match MBPs to placeholder keys.

    Returns an MbpAnalysis with per-element tier classification and line metrics.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    page_width = doc[0].rect.width
    max_page = doc.page_count
    doc.close()

    visual_lines = extract_visual_lines(pdf_path)
    elements = group_into_elements(visual_lines, page_width)

    # Reference width: 75th percentile of visual-line widths
    all_widths = sorted(
        vl.x_max - vl.x_min for vl in visual_lines if (vl.x_max - vl.x_min) > 20
    )
    ref_width = (
        all_widths[int(len(all_widths) * 0.75)] if all_widths else page_width * 0.8
    )

    # Avg chars per full line by element kind (only lines with fill >= tier_b)
    bullet_chars: list[int] = []
    para_chars: list[int] = []

    for elem in elements:
        for i, vl in enumerate(elem.lines):
            w = vl.x_max - vl.x_min
            fill = w / ref_width if ref_width > 0 else 0
            is_last_of_mbp = (i == elem.line_count - 1) and elem.is_mbp
            if fill >= tier_b_thresh and not is_last_of_mbp:
                (bullet_chars if elem.kind == "bullet" else para_chars).append(
                    vl.char_count
                )

    avg_bullet = sum(bullet_chars) / len(bullet_chars) if bullet_chars else 0.0
    avg_para = sum(para_chars) / len(para_chars) if para_chars else 0.0
    lines_on_last = sum(1 for vl in visual_lines if vl.page_num == max_page)

    # Fuzzy-match MBP elements to placeholder keys
    match_threshold = 0.55
    used_keys: set[str] = set()
    mbp_details: list[MbpDetail] = []

    for elem in elements:
        if not elem.is_mbp:
            continue
        if elem.kind == "heading":
            continue

        last = elem.last_line
        if last is None:
            continue

        last_w = last.x_max - last.x_min
        last_fill = min(last_w / ref_width, 1.0) if ref_width > 0 else 0.0

        if last_fill < tier_a_thresh:
            tier = "A"
        elif last_fill < tier_b_thresh:
            tier = "B"
        else:
            tier = "C"

        clean = _norm(_STRIP_BULLETS_RE.sub("", elem.full_text).strip())
        if not clean:
            continue

        best_key: str | None = None
        best_ratio = match_threshold

        for key, value in mod_fields.items():
            if key in used_keys:
                continue
            if isinstance(value, str) and value.strip() == REMOVE_SENTINEL:
                continue
            ratio = SequenceMatcher(None, clean, _norm(str(value))).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key

        if best_key is None:
            continue

        # Skip template-combined keys (names, roles, urls, tech stacks)
        # whose rendered text includes dates/labels the LLM cannot control
        if best_key.endswith(_SKIP_KEY_SUFFIXES):
            used_keys.add(best_key)
            continue

        # 1-line capacity with overhead margin for bullets
        if elem.kind == "bullet":
            cap = max(1, int(avg_bullet) - BULLET_OVERHEAD)
        else:
            cap = max(1, int(avg_para))

        val_len = len(mod_fields[best_key])
        chars_over = max(0, val_len - cap)

        used_keys.add(best_key)
        mbp_details.append(MbpDetail(
            key=best_key,
            value=mod_fields[best_key],
            kind=elem.kind,
            visual_line_count=elem.line_count,
            last_line_fill=round(last_fill, 3),
            last_line_chars=last.char_count,
            last_line_text=last.text,
            total_chars=val_len,
            one_line_cap=cap,
            chars_over=chars_over,
            tier=tier,
        ))

    return MbpAnalysis(
        mbp_details=mbp_details,
        avg_chars_per_bullet_line=round(avg_bullet, 1),
        avg_chars_per_para_line=round(avg_para, 1),
        total_visual_lines=len(visual_lines),
        lines_on_last_page=lines_on_last,
        ref_width=round(ref_width, 1),
    )
