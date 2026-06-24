from pathlib import Path
from typing import Dict, Optional
import shutil

from .file_type_base import FileType
from .jinja2_render import render_and_generate
from .context_helpers import escape_chars

class TXTf(FileType):    
    def get_resume_str(self)->str:
        with open(self.res_path, 'r', encoding='utf-8') as f:
            r = f.read()
        return r
    
    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None) -> Path:
        self.context = escape_chars(context, self.res_path.name)

        working_copy_path = self._build_output_path(metadata, strip_last_suffix=True)
        shutil.copy2(self.res_path, working_copy_path)

        render_and_generate(self.context, self.res_path, working_copy_path)
        return working_copy_path
