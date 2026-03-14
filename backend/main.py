from pathlib import Path
from typing import Dict
import argparse
import json
import sys

from backend.llm_integration.AI_API.api_scripts.contracts import LLM_I, MOD_DEG, LLM_O
from backend.llm_integration.LLM_CALL import CALL, CALL_RAW, MODELS, DEFAULT_MODEL
from backend.parsers_and_generators.context_helpers import resolve_placeholders

from backend.parsers_and_generators.file_type_base import FileType
from backend.parsers_and_generators.file_type_txt_j2 import TXTf
from backend.parsers_and_generators.file_type_tex_j2 import J2f
from backend.parsers_and_generators.file_type_docx import DOCXf
from backend.parsers_and_generators.file_type_pdf import PDFf

GATEWAY_DIR       = Path(__file__).resolve().parent
RESUME_NAME: str  = ""
RESUME_PATH       = (GATEWAY_DIR / "templates" / "resume" / RESUME_NAME).resolve()
PLACEHOLDERS_PATH = (GATEWAY_DIR / "fields.json").resolve()
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
    "tex": "BASE_TEMPLATE.tex.j2",
    "txt": "BASE_TEMPLATE.txt.j2",
    "pdf": "BASE_RESUME_TEMPL.pdf", #actually, we don't support pdf yet. placeholder for future support.
}


def main(
    opcode: int,
    model: str | None = None,
    job_posting_path: Path | None = None,
    output_format: str = "json",
    mod_deg: MOD_DEG = MOD_DEG.LOW,
    faux: bool = False,
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
            llm_response: LLM_O = CALL(payload, model=model)
            mod_fields   = llm_response["placeholders"]
            changes_made = llm_response["changes_made"]
            print("--- LLM Response ---")
            print(json.dumps(llm_response, indent=2))
            print("--------------------\n")
    else:
        mod_fields   = fields
        changes_made = "-"
        print("(no LLM call — using original placeholders)")

    # Merge sensitive fields + LLM-modified placeholders, then resolve
    # recursive {{ PLACEHOLDER }} references before passing to Jinja2
    context: Dict[str, str | None] = dict(sensitive_fields)
    context.update(mod_fields)
    context = resolve_placeholders(context)

    clean_context: Dict[str, str] = {k: v for k, v in context.items() if v is not None}

    run_metadata = {
        "model":   model,
        "posting": str(posting_path),
        "moddeg":  mod_deg.value,
        "faux":    faux,
    }
    ft.post_llm_process(clean_context, metadata=run_metadata)


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
  python -m backend.main -n -p posting_3.txt -f doc\
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
            "      --model, --output, --moddeg, and --faux require an LLM call.\n"
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

    args = parser.parse_args()

    # Enforce: --no is incompatible with LLM-only flags
    if not args.do_call:
        llm_only = {
            "--model":   args.model   != DEFAULT_MODEL,
            "--output":  args.output_format != "json",
            "--moddeg":  args.mod_deg != MOD_DEG.LOW.value,
            "--faux":    args.faux,
        }
        offenders = [flag for flag, was_set in llm_only.items() if was_set]
        if offenders:
            parser.error(
                f"-n/--no cannot be used with: {', '.join(offenders)}  "
                "(these flags have no effect without an LLM call)"
            )

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
        print(f"Faux   : {args.faux}\n")
        main(
            0,
            model=args.model,
            job_posting_path=posting_path,
            output_format=args.output_format,
            mod_deg=mod_deg_map[args.mod_deg],
            faux=args.faux,
        )
    else:
        print(f"Posting: {posting_path.name}  (no LLM call)\n")
        main(1, job_posting_path=posting_path)
