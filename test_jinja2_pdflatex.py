import sys
from jinja2 import Environment, FileSystemLoader
from pdflatex import PDFLaTeX
from dotenv import load_dotenv, dotenv_values

BASE_RESUME_JINJA_TEMPLATE = "BASE_RESUME_TEMPL.tex.j2"
RENDERED_TEX = "main.tex"

# pre-processing before PDF compilation ....................................

load_dotenv()

ctx = dotenv_values(".env")

env = Environment(
    loader=FileSystemLoader("."),
    autoescape=False,
)
template = env.get_template(BASE_RESUME_JINJA_TEMPLATE)
rendered = template.render(**ctx)

try:
    with open(RENDERED_TEX, "w", encoding="utf-8") as f:
        f.write(rendered)
except OSError as e:
    print(f"Error: could not write '{RENDERED_TEX}': {e}", file=sys.stderr)
    sys.exit(1)

# compile to PDF ..............................................
"""
pdfl = PDFLaTeX.from_texfile('main.tex')
pdf, log, completed_process = pdfl.create_pdf(keep_pdf_file=True, keep_log_file=True)
"""
# for some reason, the above 2 lines aren't enough (the official pypi instructions)
# This is fixed by the following (i haven't investigated why):
"""
pdfl = PDFLaTeX.from_texfile('main.tex')
pdfl.set_interaction_mode()  # setting interaction mode to None.
pdf, log, completed_process = pdfl.create_pdf(keep_pdf_file=True, keep_log_file=True)
"""

pdfl = PDFLaTeX.from_texfile(RENDERED_TEX)
pdfl.set_interaction_mode()
pdf, log, proc = pdfl.create_pdf(
    keep_pdf_file=True,
    keep_log_file=True
)

if proc.returncode == 0:
    print(f"PDF generated: {RENDERED_TEX.replace('tex', 'pdf')}")
else:
    print(f"pdflatex failed; check {RENDERED_TEX.replace('.tex', '')}.log for errors")
