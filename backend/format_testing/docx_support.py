from os import PathLike
from typing import Union
import docx2txt
from docxtpl import DocxTemplate
from re import search
import time
from pathlib import Path
import shutil

def get_full_resume_from_docx(path:str)->str:
    return docx2txt.process(path)

def post_llm_process_docx(res_path: Union[str, PathLike], context)->None:
    orig = Path(res_path)
    timestamp = int(time.time())    
    working_copy = orig.with_name(f"{orig.stem}_{timestamp}{orig.suffix}")
    shutil.copy2(orig, working_copy)

    doc = DocxTemplate(working_copy)
    doc.init_docx()
   
    def render_fully(doc:DocxTemplate, context, max_passes=10):
        for _i in range(max_passes):
            xml = doc.get_xml()
            if not search(r"{{\s*[^}]+\s*}}", xml):
                break
            doc.render(context)
            try:
                doc.save(working_copy)
            except Exception as e:
                print(f"Save-after-render failed: {e}")
            else:
                print(f"Save-after-render good -> {working_copy}")
        else:
            raise RuntimeError("Too many nested rendering passes")

    try:
        render_fully(doc, context)
    except Exception as e:
        print(f"Render failed: {e}")
    else:
        print(f"Render good.")
