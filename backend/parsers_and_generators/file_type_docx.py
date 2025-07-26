from os import PathLike
from typing import Union, Optional, Dict
import docx2txt
from docxtpl import DocxTemplate
from re import search
import time
from pathlib import Path
import shutil

from file_type_base import FileType

class DOCXf(FileType):
    def get_resume_str(self, res_path:str)->str:
        return docx2txt.process(res_path)

    def post_llm_process(self, res_path: Union[str, PathLike], context: Dict[str, str], output_dir: Optional[Union[str, PathLike]] = None)->None:
        orig =  Path(res_path)
        if output_dir is not None:
            dest_dir = Path(output_dir)
        else:
            dest_dir = orig.parent
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"destination folder dne: {e}")
        else:
            pass
        timestamp = int(time.time())
        new_name = f"{orig.stem}_{timestamp}{orig.suffix}"
        working_copy = dest_dir / new_name
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
