from jinja2 import Environment, FileSystemLoader
from typing import Dict
from pathlib import Path
from typing import Union
from os import PathLike

from context_helpers import escape_chars

def render_and_generate(context: Dict[str, str], resume_path: Union[str, PathLike], output_path: Union[str, PathLike])->None:
    resume_name = Path(resume_path).name            #ex:    filename.tex.j2    |   filename.txt.j2 |   filename.docx
    resume_fname = Path(resume_path).resolve().stem #ex:    filename.tex       |   filename.txt    |   filename
    resume_parent_dir = Path(resume_path).resolve().parent    
    
    try:
        context = escape_chars(context, resume_name)
    except OSError as e:
        print(f"Escaping error: {e}")
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
