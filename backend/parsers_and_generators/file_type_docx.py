from docxtpl import DocxTemplate
from typing import Dict, Optional
import docx2txt
import shutil
import time

from .file_type_base import FileType, build_output_tag
from .context_helpers import escape_chars

class DOCXf(FileType):
    def get_resume_str(self)->str:
        return docx2txt.process(self.res_path)

    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None)->None:        
        self.context = escape_chars(context, "docx")

        orig = self.res_path
        timestamp = int(time.time())
        tag = build_output_tag(metadata)
        new_name = f"{orig.stem}{tag}_{timestamp}{orig.suffix}"
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
