from jinja2 import Environment, FileSystemLoader
from typing import Any, Dict, Optional
from pathlib import Path
from typing import Union
from os import PathLike
import re

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

    # 2) If it's a dict, recurse on each value
    if isinstance(ctx, dict):
        return {k: escape_context(v, _LATEX_ESC, _LATEX_ESC_RE)
                for k, v in ctx.items()}

    # 3) If it's a list or tuple, recurse in order
    if isinstance(ctx, list):
        return [escape_context(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx]
    if isinstance(ctx, tuple):
        return tuple(escape_context(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx)

    # 4) Otherwise leave it alone (ints, None, etc.)
    return ctx

def render_and_generate(context: Dict[str, str], resume_path: Union[str, PathLike], output_path: Union[str, PathLike])->None:
    resume_name = Path(resume_path).name #example: filename.tex.j2 or filename.txt.j2
    resume_fname = Path(resume_path).resolve().stem #ex: filename.tex or filename.txt
    resume_parent_dir = Path(resume_path).resolve().parent
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
