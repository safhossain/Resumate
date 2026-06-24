from jinja2 import Environment, FileSystemLoader
from typing import Dict
from pathlib import Path
from typing import Union
from os import PathLike


def render_and_generate(context: Dict[str, str], resume_path: Union[str, PathLike], output_path: Union[str, PathLike])->None:
    """Render *context* into the Jinja2 template at *resume_path* → *output_path*.

    Pure render: callers are responsible for escaping placeholder values
    (see ``context_helpers.escape_chars``) before calling this.
    """
    resume_name = Path(resume_path).name            #ex:    filename.tex.j2    |   filename.txt.j2 |   filename.docx
    resume_fname = Path(resume_path).resolve().stem #ex:    filename.tex       |   filename.txt    |   filename
    resume_parent_dir = Path(resume_path).resolve().parent    

    is_tex = resume_name.endswith((".tex.j2", ".tex"))

    env = Environment(
        loader=FileSystemLoader(resume_parent_dir),
        autoescape=False,
        variable_start_string="(((" if is_tex else "{{",
        variable_end_string=")))" if is_tex else "}}",
        comment_start_string="{##" if is_tex else "{#",
        comment_end_string="##}" if is_tex else "#}",
        block_start_string="{%%" if is_tex else "{%",
        block_end_string="%%}" if is_tex else "%}",
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
