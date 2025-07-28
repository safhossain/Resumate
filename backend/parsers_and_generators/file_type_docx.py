from docxtpl import DocxTemplate
from typing import Dict
import docx2txt
import shutil
import time

from file_type_base import FileType

class DOCXf(FileType):
    def get_resume_str(self)->str:
        return docx2txt.process(self.res_path)

    def post_llm_process(self, context: Dict[str, str])->None:        
        self.context = context

        orig = self.res_path
        timestamp = int(time.time())
        new_name = f"{orig.stem}_{timestamp}{orig.suffix}"
        working_copy = self.dest_dir / new_name
        shutil.copy2(orig, working_copy)

        doc = DocxTemplate(working_copy)
        doc.init_docx()
        
        doc.render(self.context)
        try:
            doc.save(working_copy)
        except OSError as e:
            print(f"Render failed: {e}")
        else:
            print(f"Render good.")
