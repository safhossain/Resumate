from os import PathLike
from typing import Union
import docx2txt
from docxtpl import DocxTemplate
from re import search
import time
from pathlib import Path

def get_full_resume_from_docx(path:str)->str:
    return docx2txt.process(path)

def post_llm_process_docx(res_path: Union[str, PathLike], context)->None:
    RESUME_PATH = res_path

    doc = DocxTemplate(RESUME_PATH)
    doc.init_docx()

    orig        = Path(RESUME_PATH)
    timestamp   = int(time.time())
    new_name    = f"{orig.stem}_{timestamp}{orig.suffix}"
    output_path = orig.with_name(new_name)

    def render_fully(doc:DocxTemplate, context, max_passes=10):
        for _i in range(max_passes):
            xml = doc.get_xml()
            if not search(r"{{\s*[^}]+\s*}}", xml):
                break
            doc.render(context)
            try:
                doc.save(output_path)
            except Exception as e:
                print(f"Save failed: {e}")
            else:
                print(f"Saved -> {output_path}")
        else:
            raise RuntimeError("Too many nested rendering passes")

    try:
        render_fully(doc, context)
    except Exception as e:
        print(f"Render failed: {e}")
    else:
        print(f"Render good.")
