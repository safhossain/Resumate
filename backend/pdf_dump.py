"""
Raw PyMuPDF diagnostic dump.  Shows exactly what fitz.get_text("dict") reports
for each block, line, and span — including bounding boxes and text.

Usage:
  python -m backend.pdf_dump <path_to_pdf> [--page N]

If --page is omitted, dumps all pages.
"""

import argparse
import sys
import io
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid UnicodeEncodeError with special chars
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def dump_pdf(pdf_path: Path, page_num: int | None = None) -> None:
    import fitz

    doc = fitz.open(str(pdf_path))
    page_width = doc[0].rect.width
    page_height = doc[0].rect.height
    print(f"PDF: {pdf_path.name}  |  {doc.page_count} page(s)  |  page size: {page_width:.1f} x {page_height:.1f} pts")
    print()

    pages_to_dump = [page_num - 1] if page_num else range(doc.page_count)

    for pi in pages_to_dump:
        page = doc[pi]
        pd = page.get_text("dict")
        pw = page.rect.width

        print(f"{'='*80}")
        print(f"PAGE {pi + 1}  (width={pw:.1f}pt, height={page.rect.height:.1f}pt)")
        print(f"{'='*80}")

        blocks = pd.get("blocks", [])
        for b_idx, block in enumerate(blocks):
            btype = block.get("type", 0)
            bbox = block.get("bbox", (0, 0, 0, 0))
            bx0, by0, bx1, by1 = bbox
            bw = bx1 - bx0

            if btype == 1:
                print(f"\n  BLOCK {b_idx} [IMAGE]  bbox=({bx0:.1f}, {by0:.1f}, {bx1:.1f}, {by1:.1f})  w={bw:.1f}")
                continue

            lines = block.get("lines", [])
            block_text_preview = " ".join(
                " ".join(sp.get("text", "") for sp in ln.get("spans", []))
                for ln in lines
            ).strip()
            if len(block_text_preview) > 120:
                block_text_preview = block_text_preview[:117] + "..."

            print(f"\n  BLOCK {b_idx} [{len(lines)} pymupdf-line(s)]  "
                  f"bbox=({bx0:.1f}, {by0:.1f}, {bx1:.1f}, {by1:.1f})  w={bw:.1f}  "
                  f"fill={bw/pw:.0%}")
            print(f"    text: \"{block_text_preview}\"")

            for l_idx, line in enumerate(lines):
                lbbox = line.get("bbox", (0, 0, 0, 0))
                lx0, ly0, lx1, ly1 = lbbox
                lw = lx1 - lx0
                spans = line.get("spans", [])
                line_text = " ".join(sp.get("text", "") for sp in spans).strip()

                print(f"    LINE {l_idx}  bbox=({lx0:.1f}, {ly0:.1f}, {lx1:.1f}, {ly1:.1f})  "
                      f"w={lw:.1f}  fill={lw/pw:.0%}  "
                      f"y_mid={((ly0+ly1)/2):.1f}  "
                      f"chars={len(line_text)}")
                print(f"      text: \"{line_text}\"")

                for s_idx, span in enumerate(spans):
                    sbbox = span.get("bbox", (0, 0, 0, 0))
                    sx0, sy0, sx1, sy1 = sbbox
                    sw = sx1 - sx0
                    stext = span.get("text", "")
                    sfont = span.get("font", "?")
                    ssize = span.get("size", 0)
                    if len(spans) > 1:
                        print(f"        SPAN {s_idx}  bbox=({sx0:.1f}, {sy0:.1f}, {sx1:.1f}, {sy1:.1f})  "
                              f"w={sw:.1f}  font={sfont}  size={ssize:.1f}  "
                              f"\"{stext}\"")

        print()

    doc.close()


def main():
    parser = argparse.ArgumentParser(description="Dump raw PyMuPDF block/line/span data from a PDF.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--page", type=int, default=None, help="Dump only this page number (1-based)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} does not exist.")
        sys.exit(1)

    dump_pdf(pdf_path, args.page)


if __name__ == "__main__":
    main()
