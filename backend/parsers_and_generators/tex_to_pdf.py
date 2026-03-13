from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union
from os import PathLike

def gen_pdf(tex_file: Union[str, PathLike, Path],
            outdir: Optional[Union[str, PathLike, Path]] = None) -> Path:
    """
    Build a PDF from a .tex file using pdflatex, writing the PDF into `outdir`
    (defaults to the .tex file's directory). Returns the destination PDF path.
    """
    tex = Path(tex_file).expanduser()
    if not tex.exists():
        raise FileNotFoundError(f"Input not found: {tex}")

    if tex.suffix.lower() != ".tex":
        raise ValueError(f"Expected a .tex file, got: {tex.name}")

    # Where to place the final PDF
    out_dir = Path(outdir).expanduser() if outdir is not None else tex.parent
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run LaTeX *from the .tex file's folder* so relative \\input / \\includegraphics work.
    workdir = tex.parent.resolve()

    with tempfile.TemporaryDirectory() as build_dir:
        build_dir_path = Path(build_dir)

        cmd = [
            "pdflatex",
            "-halt-on-error",
            "-file-line-error",
            "-interaction=nonstopmode",
            "-output-directory", str(build_dir_path),
            tex.name,  # only the filename, because we set cwd=workdir
        ]
        try:
            subprocess.run(cmd, cwd=workdir, check=True)
        except FileNotFoundError:
            raise RuntimeError("pdflatex not found on PATH. Install TeX Live/MiKTeX or add it to PATH.")
        except subprocess.CalledProcessError as e:
            # Leave aux files in tmp; show a helpful message
            raise RuntimeError(f"pdflatex failed with exit code {e.returncode}. Check your LaTeX log.") from e

        src_pdf = build_dir_path / f"{tex.stem}.pdf"
        if not src_pdf.exists():
            raise RuntimeError("Expected PDF was not produced. Check LaTeX errors/warnings.")

        dst_pdf = out_dir / src_pdf.name
        shutil.move(str(src_pdf), str(dst_pdf))
        print(f"PDF generated at {dst_pdf}")
        return dst_pdf

def main() -> None:
    parser = argparse.ArgumentParser(description="Compile a .tex file to PDF using pdflatex.")
    parser.add_argument("-i", "--input", type=Path, required=True,
                        help="Path to the .tex file (relative to your shell's pwd or absolute).")
    parser.add_argument("-o", "--outdir", type=Path, default=None,
                        help="Directory to write the PDF. Defaults to the .tex file's directory.")
    args = parser.parse_args()
    gen_pdf(args.input, args.outdir)

if __name__ == "__main__":
    main()
