from pathlib import Path
from typing import Dict
import argparse
import json
import shutil
import sys
import tempfile
import time

from backend.llm_integration.AI_API.api_scripts.contracts import LLM_I, MOD_DEG, LLM_O
from backend.llm_integration.LLM_CALL import (
    CALL, CALL_RAW,
    CALL_RETRY, CALL_RETRY2,
    CALL_RETRY_TEX, CALL_RETRY2_TEX,
    MODELS, DEFAULT_MODEL,
)
from backend.parsers_and_generators.page_count_docx import get_docx_page_info, analyze_mbps_from_docx
from backend.parsers_and_generators.page_info import get_pdf_page_info
from backend.parsers_and_generators.visual_lines import analyze_mbps
from backend.parsers_and_generators.context_helpers import resolve_placeholders

from backend.parsers_and_generators.file_type_base import FileType
from backend.parsers_and_generators.file_type_txt_j2 import TXTf
from backend.parsers_and_generators.file_type_tex_j2 import J2f
from backend.parsers_and_generators.file_type_docx import DOCXf
from backend.parsers_and_generators.file_type_pdf import PDFf

GATEWAY_DIR       = Path(__file__).resolve().parent
RESUME_NAME: str  = ""
RESUME_PATH       = (GATEWAY_DIR / "templates" / "resume" / RESUME_NAME).resolve()
#PLACEHOLDERS_PATH = (GATEWAY_DIR / "fields.json").resolve()
PLACEHOLDERS_PATH = (GATEWAY_DIR / "fields_docx.json").resolve()
POSTING_DIR       = (GATEWAY_DIR / "postings_new").resolve()
DEFAULT_POSTING   = "posting_1.txt"
ACC_PATH          = (GATEWAY_DIR / "resources" / "ACC.txt").resolve()
SENSITIVE_PATH    = (GATEWAY_DIR / "sensitive_fields.json").resolve()
OUTPUT_DIR        = (GATEWAY_DIR / "outputs").resolve()

HANDLERS: dict[tuple[str, ...], type[FileType]] = {
    (".tex", ".j2"): J2f,
    (".txt", ".j2"): TXTf,
    (".doc",):       DOCXf,
    (".docx",):      DOCXf,
    (".pdf",):       PDFf,
}

TEMPLATE_MAP = {
    "doc": "BASE_TEMPLATE.docx",
    "tex": "BASE_TEMPLATE_2.tex.j2",
    "txt": "BASE_TEMPLATE.txt.j2",
    "pdf": "BASE_RESUME_TEMPL.pdf", #actually, we don't support pdf yet. placeholder for future support.
}


def _print_placeholder_summary(placeholders: dict, label: str = "Placeholder char counts") -> None:
    """Print a concise table of placeholder lengths, sorted descending."""
    sorted_items = sorted(placeholders.items(), key=lambda kv: len(kv[1]), reverse=True)
    total = sum(len(v) for v in placeholders.values())
    width = max((len(k) for k in placeholders), default=10)
    print(f"  {'KEY':<{width}}  LEN")
    print(f"  {'-'*width}  ---")
    for k, v in sorted_items:
        marker = "  ← REMOVE_BULLETPOINT" if v.strip() == "REMOVE_BULLETPOINT" else ""
        print(f"  {k:<{width}}  {len(v):>4}{marker}")
    print(f"  {'-'*width}  ---")
    print(f"  {'TOTAL':<{width}}  {total:>4}  ({len(placeholders)} placeholders)")


def main(
    opcode: int,
    model: str | None = None,
    job_posting_path: Path | None = None,
    output_format: str = "json",
    mod_deg: MOD_DEG = MOD_DEG.LOW,
    faux: bool = False,
    pages: int | None = None,
    auto_retry: bool = False,
) -> None:
    with open(PLACEHOLDERS_PATH, encoding="utf-8") as f:
        fields = json.load(f)

    posting_path = job_posting_path or (POSTING_DIR / DEFAULT_POSTING)
    with open(posting_path, "r", encoding="utf-8") as f:
        JOB_DESCRIPTION = f.read()

    with open(ACC_PATH, "r", encoding="utf-8") as f:
        ACC = f.read()

    with open(SENSITIVE_PATH, encoding="utf-8") as f:
        sensitive_fields = json.load(f)

    # Determine file-handler from resume suffix(es)
    suffixes = tuple(s.lower() for s in RESUME_PATH.suffixes)
    key = suffixes[-2:] if suffixes[-2:] in HANDLERS else (suffixes[-1],)
    try:
        Handler = HANDLERS[key]
    except KeyError:
        raise ValueError("Resume file must be one of: .docx, .doc, .txt.j2, .pdf, or .tex.j2")

    ft = Handler(RESUME_PATH, OUTPUT_DIR)
    FULL_RESUME_STR = ft.get_resume_str()

    # Merge sensitive fields + LLM-modified placeholders, then resolve
    # recursive {{ PLACEHOLDER }} references before passing to Jinja2
    def _build_context(placeholder_values: dict) -> Dict[str, str]:
        ctx: Dict[str, str | None] = dict(sensitive_fields)
        ctx.update(placeholder_values)
        ctx = resolve_placeholders(ctx)
        return {k: v for k, v in ctx.items() if v is not None}

    payload: LLM_I = {
        "full_resume": FULL_RESUME_STR,
        "placeholders": fields,
        "mod_deg": mod_deg,
        "faux": faux,
        "job_posting": JOB_DESCRIPTION,
        "acc": ACC,
    }

    if opcode != 1:
        if output_format == "stream":
            raw = CALL_RAW(payload, model=model)
            print("--- Raw LLM Response ---")
            print(raw)
            return
        else:
            print("--- Input placeholder char counts ---")
            _print_placeholder_summary(fields)
            print()

            # Pre-render with original placeholders to establish baseline metrics
            baseline_fields = None
            if pages is not None and Handler in (DOCXf, J2f):
                print("--- Pre-render baseline (original placeholders) ---")
                pre_context = _build_context(fields)
                tmp_dir = Path(tempfile.mkdtemp(prefix="resumate_prerender_"))
                try:
                    pre_ft = Handler(RESUME_PATH, tmp_dir)
                    pre_meta = {"timestamp": int(time.time()), "suffix": "_prerender"}
                    pre_output = pre_ft.post_llm_process(pre_context, metadata=pre_meta)

                    is_tex = (Handler is J2f)
                    if is_tex:
                        pre_info = get_pdf_page_info(pre_output)
                    else:
                        pre_info = get_docx_page_info(pre_output)

                    if pre_info:
                        pre_pages = pre_info["page_count"]
                        pre_fill = round(pre_info["last_page_fill_pct"] * 100)
                        print(f"  Pre-render: {pre_pages} page(s), last page ~{pre_fill}% filled")
                    else:
                        print("  Pre-render: page info unavailable")

                    baseline_fields = fields
                    print(f"  Baseline char budgets will be injected into first LLM call.")
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                print()

            llm_response: LLM_O = CALL(
                payload, model=model, page_hint=pages,
                baseline_fields=baseline_fields,
            )
            mod_fields   = llm_response["placeholders"]
            changes_made = llm_response["changes_made"]
            print("--- LLM Response ---")
            print(json.dumps(llm_response, indent=2))
            print("--------------------\n")
    else:
        mod_fields   = fields
        changes_made = "-"
        print("(no LLM call — using original placeholders)")

    run_timestamp = int(time.time())
    run_metadata = {
        "model":     model,
        "posting":   str(posting_path),
        "moddeg":    mod_deg.value,
        "faux":      faux,
        "timestamp": run_timestamp,
    }

    clean_context = _build_context(mod_fields)
    output_path = ft.post_llm_process(clean_context, metadata=run_metadata)

    # Page-limit check (docx and tex; docx requires LibreOffice on PATH)
    if pages is not None and Handler in (DOCXf, J2f) and opcode != 1:
        is_tex = (Handler is J2f)
        fmt_label = "LaTeX/PDF" if is_tex else "DOCX"

        # J2f output is already a PDF; DOCXf needs LibreOffice → PDF conversion
        if is_tex:
            page_info = get_pdf_page_info(output_path)
        else:
            page_info = get_docx_page_info(output_path)

        if page_info is None:
            print("Page check: skipped (see warnings above).")
        else:
            actual_pages = page_info["page_count"]
            fill_pct     = page_info["last_page_fill_pct"]
            fill_display = f"{round(fill_pct * 100)}%"

            if actual_pages <= pages:
                print(f"Page check ({fmt_label}): {actual_pages} page(s), last page {fill_display} filled — within target ({pages}). ✓")
            else:
                print(f"Page check ({fmt_label}): {actual_pages} page(s), last page {fill_display} filled — exceeds target ({pages}). Retrying with LLM...")

                print("  Running MBP analysis on initial render...")
                if is_tex:
                    mbp_analysis = analyze_mbps(output_path, mod_fields)
                else:
                    mbp_analysis = analyze_mbps_from_docx(output_path, mod_fields)

                if mbp_analysis is not None:
                    _ma = mbp_analysis
                    _ta, _tb, _tc = len(_ma.tier_a), len(_ma.tier_b), len(_ma.tier_c)
                    print(f"  MBP analysis: {len(_ma.mbp_details)} matched "
                          f"({_ta} Tier A, {_tb} Tier B, {_tc} Tier C)")
                    print(f"  Avg chars/bullet line: ~{_ma.avg_chars_per_bullet_line:.0f}  |  "
                          f"Avg chars/para line: ~{_ma.avg_chars_per_para_line:.0f}  |  "
                          f"Last page: {_ma.lines_on_last_page} visual lines")
                    for d in _ma.tier_a:
                        overflow = d.last_line_text[:60] + ("..." if len(d.last_line_text) > 60 else "")
                        print(f"    [A] {d.key}: {d.total_chars}ch → {d.visual_line_count} lines, "
                              f"cap {d.one_line_cap}, cut ≥{d.chars_over}  "
                              f'overflow: "{overflow}"')
                    for d in _ma.tier_b:
                        overflow = d.last_line_text[:60] + ("..." if len(d.last_line_text) > 60 else "")
                        print(f"    [B] {d.key}: {d.total_chars}ch → {d.visual_line_count} lines, "
                              f"cap {d.one_line_cap}, cut ≥{d.chars_over}  "
                              f'overflow: "{overflow}"')
                else:
                    print("  MBP analysis unavailable.")

                retry_payload: LLM_I = {
                    **payload,
                    "placeholders": mod_fields,
                }

                print(f"\n--- Retry prompt summary ---")
                print(f"  Detected : {actual_pages} page(s), last page ~{fill_display} filled  →  Target: {pages} page(s)")
                print(f"  Model    : {model}  |  moddeg: {mod_deg.value}  |  faux: {faux}")
                print(f"  Strategy : line-budget — MBP rephrasing + REMOVE_BULLETPOINT")
                print(f"  Current placeholder char counts (from first LLM response):")
                _print_placeholder_summary(mod_fields)
                print()

                if is_tex:
                    llm_retry: LLM_O = CALL_RETRY_TEX(
                        retry_payload,
                        actual_pages=actual_pages,
                        target_pages=pages,
                        last_page_fill_pct=fill_pct,
                        mbp_analysis=mbp_analysis,
                        model=model,
                    )
                else:
                    llm_retry = CALL_RETRY(
                        retry_payload,
                        actual_pages=actual_pages,
                        target_pages=pages,
                        last_page_fill_pct=fill_pct,
                        mbp_analysis=mbp_analysis,
                        model=model,
                    )

                retry_fields = llm_retry["placeholders"]
                print("--- Retry LLM Response ---")
                print(json.dumps(llm_retry, indent=2))
                print("--------------------------\n")
                print("--- Retry placeholder char counts (post-retry) ---")
                _print_placeholder_summary(retry_fields)
                print()

                clean_retry_context = _build_context(retry_fields)
                retry_output_path = ft.post_llm_process(
                    clean_retry_context,
                    metadata={**run_metadata, "suffix": "_retry"},
                )

                if is_tex:
                    retry_info = get_pdf_page_info(retry_output_path)
                else:
                    retry_info = get_docx_page_info(retry_output_path)

                if retry_info is None:
                    print("Page check after retry: skipped (see warnings above).")
                else:
                    retry_pages        = retry_info["page_count"]
                    retry_fill_pct     = retry_info["last_page_fill_pct"]
                    retry_fill_display = f"{round(retry_fill_pct * 100)}%"
                    if retry_pages <= pages:
                        print(f"Page check after retry: {retry_pages} page(s), last page {retry_fill_display} filled — within target ({pages}). ✓")
                    else:
                        print(
                            f"WARNING: Output is still {retry_pages} page(s) (last page {retry_fill_display} filled) "
                            f"after retry (target: {pages})."
                        )

                        print("  Running MBP analysis on retry output...")
                        if is_tex:
                            retry_mbp_analysis = analyze_mbps(retry_output_path, retry_fields)
                        else:
                            retry_mbp_analysis = analyze_mbps_from_docx(retry_output_path, retry_fields)

                        if retry_mbp_analysis is not None:
                            _rma = retry_mbp_analysis
                            _rta, _rtb = len(_rma.tier_a), len(_rma.tier_b)
                            mbp_target_keys = [d.key for d in _rma.tier_a + _rma.tier_b]
                            print(f"  MBP analysis: {len(_rma.mbp_details)} matched "
                                  f"({_rta} Tier A, {_rtb} Tier B, {len(_rma.tier_c)} Tier C)")
                            print(f"  Avg chars/bullet line: ~{_rma.avg_chars_per_bullet_line:.0f}  |  "
                                  f"Avg chars/para line: ~{_rma.avg_chars_per_para_line:.0f}  |  "
                                  f"Last page: {_rma.lines_on_last_page} visual lines")
                            for d in _rma.tier_a:
                                overflow = d.last_line_text[:60] + ("..." if len(d.last_line_text) > 60 else "")
                                print(f"    [A] {d.key}: {d.total_chars}ch → {d.visual_line_count} lines, "
                                      f"cap {d.one_line_cap}, cut ≥{d.chars_over}  "
                                      f'overflow: "{overflow}"')
                            for d in _rma.tier_b:
                                overflow = d.last_line_text[:60] + ("..." if len(d.last_line_text) > 60 else "")
                                print(f"    [B] {d.key}: {d.total_chars}ch → {d.visual_line_count} lines, "
                                      f"cap {d.one_line_cap}, cut ≥{d.chars_over}  "
                                      f'overflow: "{overflow}"')
                        else:
                            print("  MBP analysis unavailable.")
                            retry_mbp_analysis = None
                            mbp_target_keys = []

                        print()
                        if auto_retry:
                            answer = "y"
                            print(
                                f"  Output is {retry_pages} page(s) (target: {pages}). "
                                f"Auto-starting second retry (-y flag)."
                            )
                        elif sys.stdin.isatty():
                            answer = input(
                                f"  Output is {retry_pages} page(s) (target: {pages}). "
                                f"Perform a second retry targeting widow lines? [y/N] "
                            ).strip().lower()
                        else:
                            answer = "n"
                            print(
                                f"  Output is {retry_pages} page(s) (target: {pages}). "
                                f"Second retry skipped (non-interactive mode)."
                            )

                        if answer == "y":
                            second_retry_payload: LLM_I = {
                                **payload,
                                "placeholders": retry_fields,
                            }

                            print(f"\n--- Second retry prompt summary ---")
                            print(f"  Detected : {retry_pages} page(s), last page ~{retry_fill_display} filled  →  Target: {pages} page(s)")
                            print(f"  Model    : {model}  |  moddeg: {mod_deg.value}  |  faux: {faux}")
                            print(f"  Strategy : MBP targeted rephrasing + REMOVE_BULLETPOINT")
                            if mbp_target_keys:
                                print(f"  MBP targets: {mbp_target_keys}")
                            print(f"  Current placeholder char counts (from first retry):")
                            _print_placeholder_summary(retry_fields)
                            print()

                            if is_tex:
                                llm_retry2: LLM_O = CALL_RETRY2_TEX(
                                    second_retry_payload,
                                    actual_pages=retry_pages,
                                    target_pages=pages,
                                    last_page_fill_pct=retry_fill_pct,
                                    mbp_analysis=retry_mbp_analysis,
                                    model=model,
                                )
                            else:
                                llm_retry2 = CALL_RETRY2(
                                    second_retry_payload,
                                    actual_pages=retry_pages,
                                    target_pages=pages,
                                    last_page_fill_pct=retry_fill_pct,
                                    mbp_analysis=retry_mbp_analysis,
                                    model=model,
                                )

                            retry2_fields = llm_retry2["placeholders"]
                            print("--- Second retry LLM response ---")
                            print(json.dumps(llm_retry2, indent=2))
                            print("---------------------------------\n")
                            print("--- Second retry placeholder char counts ---")
                            _print_placeholder_summary(retry2_fields)
                            print()

                            clean_retry2_context = _build_context(retry2_fields)
                            retry2_output_path = ft.post_llm_process(
                                clean_retry2_context,
                                metadata={**run_metadata, "suffix": "_retry2"},
                            )

                            if is_tex:
                                retry2_info = get_pdf_page_info(retry2_output_path)
                            else:
                                retry2_info = get_docx_page_info(retry2_output_path)

                            if retry2_info is None:
                                print("Page check after second retry: skipped (see warnings above).")
                            else:
                                r2_pages       = retry2_info["page_count"]
                                r2_fill_pct    = retry2_info["last_page_fill_pct"]
                                r2_fill_display = f"{round(r2_fill_pct * 100)}%"
                                if r2_pages <= pages:
                                    print(f"Page check after second retry: {r2_pages} page(s), last page {r2_fill_display} filled — within target ({pages}). ✓")
                                else:
                                    print(
                                        f"WARNING: Output is still {r2_pages} page(s) (last page {r2_fill_display} filled) "
                                        f"after second retry (target: {pages}). Keeping as-is."
                                    )
                        else:
                            print("  Second retry skipped. Keeping first retry output.")


if __name__ == "__main__":    

    _EXAMPLES = """\
Examples:
  # Default run (deepseek, posting_1, low mod, no faux)
  python -m backend.main

  # Claude, specific posting, render as .tex
  python -m backend.main -m claude/sonnet-4.6 -p posting_4.txt -f tex

  # Aggressive rewrite with faux skills enabled
  python -m backend.main -m deepseek/chat -p posting_2.txt --moddeg high --faux

  # Debug: see raw LLM output without writing a file
  python -m backend.main -m claude/sonnet-4.6 -p posting_4.txt -o stream

  # Skip LLM, just render template with original placeholders
  python -m backend.main -n -p posting_3.txt -f doc

  # Limit output to 1 page (docx or tex; retries if exceeded)
  python -m backend.main -m deepseek/chat -p posting_2.txt --pages 1

  # 1-page limit, auto-confirm the second retry without prompting
  python -m backend.main -m claude/sonnet-4.6 -p posting_1.txt -f tex --pages 1 -y\
"""

    if "examples" in sys.argv:
        print(_EXAMPLES)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="Resumate: generate a tailored resume via an LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Model keys (--model):\n"
            + "\n".join(f"  {k}" for k in MODELS)
            + "\n\n"
            "Note: -n/--no only accepts -f/--format and -p/--posting.\n"
            "      --model, --output, --moddeg, --faux, --pages, and -y require an LLM call.\n"
            "      -y/--yes requires --pages (no retry without a page limit).\n"
            "\n"
            "Tip: run with 'examples' to see usage examples.\n"
            "  python -m backend.main examples\n"
            "  python -m backend.main -h examples"
        ),
    )

    # LLM call toggle
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-c", "--call",
        dest="do_call",
        action="store_true",
        help="Perform an LLM call (default)",
    )
    group.add_argument(
        "-n", "--no",
        dest="do_call",
        action="store_false",
        help="Skip the LLM call; use original placeholders as-is",
    )
    parser.set_defaults(do_call=True)

    # Resume template format flag
    parser.add_argument(
        "-f", "--format",
        dest="template_format",
        choices=list(TEMPLATE_MAP),
        default="doc",
        help="Resume template format to render (default: doc)",
    )

    # LLM model flag
    parser.add_argument(
        "-m", "--model",
        dest="model",
        choices=list(MODELS),
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help=(
            f"LLM model key (default: {DEFAULT_MODEL}). "
            "Run with -h to see all available keys."
        ),
    )

    # LLM output mode flag
    parser.add_argument(
        "-o", "--output",
        dest="output_format",
        choices=["json", "stream"],
        default="json",
        help=(
            "json  - structured response, full resume pipeline (default); "
            "stream - raw LLM text for debugging, no file output"
        ),
    )

    # Job posting file flag
    parser.add_argument(
        "-p", "--posting",
        dest="posting",
        default=DEFAULT_POSTING,
        metavar="FILENAME",
        help=(
            f"Job posting filename inside postings_new/ "
            f"(default: {DEFAULT_POSTING}). "
            "Example: -p posting_3.txt"
        ),
    )

    # Modification degree flag
    parser.add_argument(
        "--moddeg",
        dest="mod_deg",
        choices=[m.value for m in MOD_DEG],
        default=MOD_DEG.LOW.value,
        help=f"How aggressively to rewrite placeholders (default: {MOD_DEG.LOW.value})",
    )

    # Faux mode flag
    parser.add_argument(
        "--faux",
        dest="faux",
        action="store_true",
        default=False,
        help="Allow LLM to introduce skills/experience not already in the resume (default: off)",
    )

    # Page limit flag
    parser.add_argument(
        "--pages",
        dest="pages",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Target maximum number of pages for the output (default: no limit). "
            "Supported for docx (requires LibreOffice) and tex (pdflatex). "
            "If the first render exceeds N pages, up to two retry LLM calls are made."
        ),
    )

    # Auto-retry flag
    parser.add_argument(
        "-y", "--yes",
        dest="auto_retry",
        action="store_true",
        default=False,
        help="Automatically run the second retry without prompting (requires --pages)",
    )

    args = parser.parse_args()

    # Validate --pages value
    if args.pages is not None and args.pages < 1:
        parser.error("--pages must be a positive integer (e.g. --pages 1)")

    # Enforce: --no is incompatible with LLM-only flags
    if not args.do_call:
        llm_only = {
            "--model":   args.model   != DEFAULT_MODEL,
            "--output":  args.output_format != "json",
            "--moddeg":  args.mod_deg != MOD_DEG.LOW.value,
            "--faux":    args.faux,
            "--pages":   args.pages is not None,
            "-y/--yes":  args.auto_retry,
        }
        offenders = [flag for flag, was_set in llm_only.items() if was_set]
        if offenders:
            parser.error(
                f"-n/--no cannot be used with: {', '.join(offenders)}  "
                "(these flags have no effect without an LLM call)"
            )

    # -y requires --pages (otherwise there's no retry to auto-confirm)
    if args.auto_retry and args.pages is None:
        parser.error("-y/--yes requires --pages N (no retry occurs without a page limit)")

    # Resolve resume template path (mutates module-level globals used by main())
    RESUME_NAME = TEMPLATE_MAP[args.template_format]
    RESUME_PATH = (GATEWAY_DIR / "templates" / "resume" / RESUME_NAME).resolve()

    posting_path = (POSTING_DIR / Path(args.posting).name).resolve()

    mod_deg_map = {m.value: m for m in MOD_DEG}

    if args.do_call:
        print(f"Model  : {args.model}")
        print(f"Posting: {posting_path.name}")
        print(f"Output : {args.output_format}")
        print(f"Mod deg: {args.mod_deg}")
        print(f"Faux   : {args.faux}")
        print(f"Pages  : {args.pages if args.pages is not None else 'no limit'}")
        print(f"AutoRetry: {args.auto_retry}\n")
        main(
            0,
            model=args.model,
            job_posting_path=posting_path,
            output_format=args.output_format,
            mod_deg=mod_deg_map[args.mod_deg],
            faux=args.faux,
            pages=args.pages,
            auto_retry=args.auto_retry,
        )
    else:
        print(f"Posting: {posting_path.name}  (no LLM call)\n")
        main(1, job_posting_path=posting_path)
