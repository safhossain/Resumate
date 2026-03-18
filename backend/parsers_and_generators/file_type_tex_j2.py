from pathlib import Path
from typing import Dict, Optional
import time

from .file_type_base import FileType, build_output_tag
from .jinja2_render import render_and_generate
from .tex_to_pdf import gen_pdf

class J2f(FileType):  

    def get_resume_str(self)->str:
        with open(self.res_path, 'r', encoding='utf-8') as f:
            j2_str = f.read()
        return j2_str
    
    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None) -> Path:
        self.context = context

        orig = self.res_path
        timestamp = int(time.time())
        tag = build_output_tag(metadata)
        all_suffixes = "".join(orig.suffixes)
        base_name = orig.name[:-len(all_suffixes)] if all_suffixes else orig.stem
        new_name = Path(f"{base_name}{tag}_{timestamp}{all_suffixes}").stem
        working_copy = self.dest_dir / new_name

        render_and_generate(self.context, self.res_path, working_copy)
        pdf_path = gen_pdf(working_copy)
        return pdf_path
