from pathlib import Path
from typing import Dict
import shutil
import time

from file_type_base import FileType
from jinja2_render import render_and_generate

class TXTf(FileType):    
    def get_resume_str(self)->str:
        with open(self.res_path, 'r', encoding='utf-8') as f:
            r = f.read()
        return r
    
    def post_llm_process(self, context: Dict[str, str])->None:
        self.context = context

        orig =  self.res_path
        timestamp = int(time.time())
        all_suffixes = "".join(orig.suffixes)
        base_name = orig.name[:-len(all_suffixes)] if all_suffixes else orig.stem
        new_name = Path(f"{base_name}_{timestamp}{all_suffixes}").stem
        working_copy_path = self.dest_dir / new_name
        shutil.copy2(orig, working_copy_path)

        render_and_generate(self.context, self.res_path, working_copy_path)
