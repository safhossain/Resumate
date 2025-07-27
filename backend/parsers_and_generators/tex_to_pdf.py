from pdflatex import PDFLaTeX
from pathlib import Path
from typing import Union
from os import PathLike
import subprocess
import tempfile
import shutil

def gen_pdf(tex_file:Union[str, PathLike])->None:
    tex = Path(tex_file)
    out_dir = tex.resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)    

    with tempfile.TemporaryDirectory() as build_dir:
        # pdflatex generates a whole bunch of auxillary files that we don't need at the end (.aux, .out, and .log files)
        # creating temp dir for all 4 files (including .pdf) and then we'll just move the .pdf file into real output dir
        subprocess.run([
            "pdflatex",
            "-halt-on-error",
            "-output-directory", build_dir,
            str(tex)
        ], check=True)

        src_pdf = Path(build_dir) / f"{tex.stem}.pdf"
        dst_pdf = out_dir / src_pdf.name
        shutil.move(str(src_pdf), str(dst_pdf)) # temp -> output_dir
        print(f"PDF generated at {dst_pdf}")
