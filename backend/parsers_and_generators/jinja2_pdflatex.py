from jinja2 import Environment, FileSystemLoader
from typing import Any, Dict, Optional
from pdflatex import PDFLaTeX
from pathlib import Path
from typing import Union
from os import PathLike
import subprocess
import argparse
import tempfile
import shutil
import re

def resolve_placeholders(ctx: Dict[str, Optional[str]], max_passes=5):
    # Note: LLM-generated
    """
    Repeatedly replace {{KEY}} in each ctx[value] with ctx[KEY], until
    no more changes occur (or max_passes is reached).
    """
    pattern = re.compile(r"{{\s*([\w]+)\s*}}")
    for _ in range(max_passes):
        changed = False
        for k, v in list(ctx.items()):
            if not isinstance(v, str):
                continue
            def repl(m):
                return ctx.get(m.group(1), "")
            new_v = pattern.sub(repl, v)
            if new_v != v:
                ctx[k] = new_v
                changed = True
        if not changed:
            break
    return ctx

def escape_context(ctx: Any,
                   _LATEX_ESC: Dict[str, str] = {
                       '\\': r'\textbackslash{}',
                       '&':  r'\&',
                       '%':  r'\%',
                       '$':  r'\$',
                       '#':  r'\#',
                       '_':  r'\_',
                       '{':  r'\{',
                       '}':  r'\}',
                       '~':  r'\textasciitilde{}',
                       '^':  r'\^{}',
                   },
                   _LATEX_ESC_RE: re.Pattern = re.compile(
                       '(' + '|'.join(re.escape(c) for c in [
                           '\\', '&', '%', '$', '#', '_', '{', '}', '~', '^'
                       ]) + ')'
                   )):
    # Note: LLM-generated
    """
    Recursively walk ctx (which might be a dict, list, tuple or scalar).
    Any str gets latex-escaped; others are kept unchanged.
    """
    # 1) If this is a string, do a single-pass escape
    if isinstance(ctx, str):
        return _LATEX_ESC_RE.sub(lambda m: _LATEX_ESC[m.group(1)], ctx)

    # 2) If it’s a dict, recurse on each value
    if isinstance(ctx, dict):
        return {k: escape_context(v, _LATEX_ESC, _LATEX_ESC_RE)
                for k, v in ctx.items()}

    # 3) If it’s a list or tuple, recurse in order
    if isinstance(ctx, list):
        return [escape_context(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx]
    if isinstance(ctx, tuple):
        return tuple(escape_context(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx)

    # 4) Otherwise leave it alone (ints, None, etc.)
    return ctx

def gen_tex(context: Dict[str, str], resume_path: Union[str, PathLike], output_path: Union[str, PathLike])->None:
    resume_name = Path(resume_path).name #filename.tex.j2
    resume_fname = Path(resume_path).resolve().stem #filename.tex    
    resume_parent_dir = Path(resume_path).resolve().parent
    '''
    Warning: Recursive {{ PLACEHOLDERS }}

    If there are {{ PLACEHOLDERS }} in the fields dict's values, then they will 
    have to be PRE-rendered inside the `context` variable first. Why can't we 
    just continously render with jinja render() function? Because:
    Jinja2 rendering will cause all jinja-like blocks, such as {% ... %} and 
    {# ... #} to be "rendered away". So what we are left with is essentially RAW .tex
    Therefore, if you try to render twice, it will cause many TemplateSyntaxError 
    messages. There probably is a best-practices for multi-rendering, but in this 
    case, the easiest possible soln is just to simulate 'rendering' for the
    context dict which will feed into being an argument for jinja's render().
    This is done below with resolve_placeholders().
    '''
    context = resolve_placeholders(context)
    
    # escaping &, %, $, #, _ etc. in the final strings
    try:
        context = escape_context(context)
    except OSError as e:
        print(f"escape_context() error: {e}")
    else:
        pass

    env = Environment(
        loader=FileSystemLoader(resume_parent_dir),
        autoescape=False
    )
    
    template = env.get_template(resume_name)
    rendered = template.render(**context)
        
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
    except OSError as e:
        print(f"Error with Rendered File Writing: {e}")
    else:
        print(f"{resume_fname} Written.")

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
    
if __name__=="__main__":
    parser = argparse.ArgumentParser(
        description="Generate TeX, PDF, or both."
    )
    parser.add_argument(
        "-t", "--tex",
        action="store_true",
        help="Only generate the .tex file"
    )
    parser.add_argument(
        "-p", "--pdf",
        action="store_true",
        help="Only generate the PDF"
    )
    
    args = parser.parse_args()

    # default to both
    if not (args.tex or args.pdf):
        args.tex = args.pdf = True
    
    if args.tex:
        gen_tex()
    
    if args.pdf:
        gen_pdf()
