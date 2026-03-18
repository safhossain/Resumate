"""
Run gateway.py across all models x active formats sequentially.
Any unknown args are forwarded to main.py (e.g. -p, --moddeg, --faux).
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_FORMATS = ["tex", "doc"]

from backend.llm_integration.LLM_CALL import MODELS

ALL_MODELS = list(MODELS.keys())


def main():
    parser = argparse.ArgumentParser(
        description="Run main.py across all models x active formats.",
        epilog=(
            "Any unrecognized args are forwarded to main.py.\n\n"
            "Examples:\n"
            "  python test_all_models.py\n"
            "  python test_all_models.py --formats tex\n"
            "  python test_all_models.py --models deepseek/chat,xai/grok-3\n"
            "  python test_all_models.py -p posting_2.txt --moddeg high --faux\n"
            "  python test_all_models.py --formats tex --models deepseek/chat -p posting_2.txt\n"
            f"\nAvailable models: {', '.join(ALL_MODELS)}\n"
            f"Active formats  : {', '.join(ACTIVE_FORMATS)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--formats",
        default=",".join(ACTIVE_FORMATS),
        help=f"Comma-separated formats to test (default: {','.join(ACTIVE_FORMATS)})",
    )
    parser.add_argument(
        "--models",
        default=",".join(ALL_MODELS),
        help="Comma-separated model keys to test (default: all)",
    )

    args, forward_args = parser.parse_known_args()

    models = [m.strip() for m in args.models.split(",")]
    formats = [f.strip() for f in args.formats.split(",")]

    combos = [(m, f) for m in models for f in formats]
    total = len(combos)

    print(f"Running {total} combinations: {len(models)} models x {len(formats)} formats")
    print(f"Models : {', '.join(models)}")
    print(f"Formats: {', '.join(formats)}")
    if forward_args:
        print(f"Extra  : {' '.join(forward_args)}")
    print("=" * 70)

    results = []

    for idx, (model, fmt) in enumerate(combos, 1):
        cmd = [
            sys.executable, "-m", "backend.main",
            "--call", "-m", model, "-f", fmt,
        ] + forward_args

        label = f"[{idx}/{total}] {model}  x  {fmt}"
        print(f"\n{'─' * 70}")
        print(label)
        print(f"  cmd: {' '.join(cmd)}")
        print(f"{'─' * 70}")

        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
        elapsed = time.time() - t0

        ok = proc.returncode == 0
        results.append((model, fmt, ok, elapsed))
        status = "OK" if ok else f"FAIL (exit {proc.returncode})"
        print(f"  -> {status}  ({elapsed:.1f}s)")

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    for model, fmt, ok, elapsed in results:
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}]  {model:30s}  {fmt:5s}  ({elapsed:.1f}s)")

    passed = sum(1 for *_, ok, _ in results if ok)
    print(f"\n  {passed}/{total} passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
