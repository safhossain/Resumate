"""
Visual-line and MBP detection metrics for any PDF.

Usage:
  # Analyze an existing PDF directly:
  python -m backend.page_metrics path/to/output.pdf

  # Render from template first, then analyze:
  python -m backend.page_metrics --render tex
  python -m backend.page_metrics --render doc
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GATEWAY_DIR = Path(__file__).resolve().parent
PLACEHOLDERS_PATH = (GATEWAY_DIR / "fields.json").resolve()
SENSITIVE_PATH = (GATEWAY_DIR / "sensitive_fields.json").resolve()
OUTPUT_DIR = (GATEWAY_DIR / "outputs").resolve()

TEMPLATE_MAP = {
    "doc": "BASE_TEMPLATE.docx",
    "tex": "BASE_TEMPLATE.tex.j2",
    "txt": "BASE_TEMPLATE.txt.j2",
}


def _resolve_placeholders(ctx):
    """Inline version -- avoids circular import issues."""
    import re
    pattern = re.compile(r"{{\s*([\w]+)\s*}}")
    for _ in range(5):
        changed = False
        for k, v in list(ctx.items()):
            if not isinstance(v, str):
                continue
            new_v = pattern.sub(lambda m: ctx.get(m.group(1), ""), v)
            if new_v != v:
                ctx[k] = new_v
                changed = True
        if not changed:
            break
    return ctx


def _render_template(fmt: str) -> Path:
    """Render a template with original placeholders and return the output path."""
    with open(PLACEHOLDERS_PATH, encoding="utf-8") as f:
        fields = json.load(f)
    with open(SENSITIVE_PATH, encoding="utf-8") as f:
        sensitive_fields = json.load(f)

    ctx = dict(sensitive_fields)
    ctx.update(fields)
    ctx = _resolve_placeholders(ctx)
    clean_context = {k: v for k, v in ctx.items() if v is not None}

    resume_name = TEMPLATE_MAP[fmt]
    resume_path = (GATEWAY_DIR / "templates" / "resume" / resume_name).resolve()
    is_tex = fmt == "tex"
    is_docx = fmt in ("doc", "docx")

    timestamp = int(time.time())
    metadata = {
        "model": "none",
        "posting": "debug",
        "moddeg": "none",
        "faux": False,
        "timestamp": timestamp,
        "suffix": "_metrics",
    }

    if is_tex:
        from backend.parsers_and_generators.file_type_tex_j2 import J2f
        ft = J2f(resume_path, OUTPUT_DIR)
        output_path = ft.post_llm_process(clean_context, metadata=metadata)
        print(f"Rendered PDF: {output_path}")
        return output_path
    elif is_docx:
        from backend.parsers_and_generators.file_type_docx import DOCXf
        ft = DOCXf(resume_path, OUTPUT_DIR)
        output_path = ft.post_llm_process(clean_context, metadata=metadata)
        print(f"Rendered DOCX: {output_path}")
        print("\nNote: DOCX visual-line analysis requires LibreOffice PDF conversion.")
        print("(visual-line dump not yet wired for DOCX; use --render tex for now)")
        sys.exit(0)
    else:
        print(f"Format '{fmt}' does not support PDF metrics.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Display visual-line / MBP metrics for a PDF.",
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default=None,
        help="Path to an existing PDF to analyze",
    )
    parser.add_argument(
        "--render", "-r",
        dest="render_fmt",
        choices=list(TEMPLATE_MAP),
        default=None,
        metavar="FMT",
        help="Render from template first (tex, doc, txt), then analyze",
    )
    args = parser.parse_args()

    if args.pdf and args.render_fmt:
        parser.error("Provide either a PDF path or --render, not both.")
    if not args.pdf and not args.render_fmt:
        parser.error("Provide a PDF path or use --render to render from template first.")

    if args.render_fmt:
        pdf_path = _render_template(args.render_fmt)
    else:
        pdf_path = Path(args.pdf).resolve()
        if not pdf_path.exists():
            print(f"ERROR: File not found: {pdf_path}")
            sys.exit(1)
        if pdf_path.suffix.lower() != ".pdf":
            print(f"ERROR: Expected a .pdf file, got: {pdf_path.name}")
            sys.exit(1)
        print(f"Analyzing: {pdf_path}")

    # ---- Page info ----
    from backend.parsers_and_generators.page_info import get_pdf_page_info
    page_info = get_pdf_page_info(pdf_path)

    print()
    print("=" * 70)
    print("PAGE INFO")
    print("=" * 70)
    if page_info:
        print(f"  Pages          : {page_info['page_count']}")
        print(f"  Last page fill : {round(page_info['last_page_fill_pct'] * 100)}%")
    else:
        print("  Page info: unavailable")

    # ---- Visual lines + MBP detection ----
    import fitz
    doc = fitz.open(str(pdf_path))
    page_width = doc[0].rect.width
    doc.close()

    from backend.parsers_and_generators.visual_lines import (
        extract_visual_lines, group_into_elements,
    )

    visual_lines = extract_visual_lines(pdf_path)
    elements = group_into_elements(visual_lines, page_width)

    content_width = page_width - 60  # approximate margins

    print()
    print("=" * 70)
    print("VISUAL LINES → LOGICAL ELEMENTS")
    print("=" * 70)

    elem_idx = 0
    mbp_count = 0
    single_count = 0

    for elem in elements:
        tag = "MBP" if elem.is_mbp else "1-LINE"
        kind_label = elem.kind.upper()
        if elem.is_mbp:
            mbp_count += 1
        else:
            single_count += 1

        print(f"\n  [{tag}] {kind_label}  (pg {elem.page_num}, {elem.line_count} visual line(s))")

        for li, vl in enumerate(elem.lines):
            width = vl.x_max - vl.x_min
            fill_pct = width / content_width if content_width > 0 else 0
            fill_display = f"{fill_pct:.0%}"

            is_last = (li == elem.line_count - 1)
            last_marker = " ← LAST" if is_last and elem.is_mbp else ""

            text_preview = vl.text
            if len(text_preview) > 100:
                text_preview = text_preview[:97] + "..."

            print(
                f"    L{li}  x=[{vl.x_min:.0f}..{vl.x_max:.0f}]  "
                f"w={width:.0f}  fill={fill_display:>4}  "
                f"chars={vl.char_count:>3}{last_marker}"
            )
            print(f"        \"{text_preview}\"")

        elem_idx += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total elements : {len(elements)}")
    print(f"  MBPs (2+ lines): {mbp_count}")
    print(f"  Single-line    : {single_count}")
    print(f"  Total visual lines: {len(visual_lines)}")
    print()


if __name__ == "__main__":
    main()
