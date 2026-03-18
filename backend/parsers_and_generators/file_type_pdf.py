from typing import Union, Optional
from pathlib import Path
from os import PathLike
import time
import shutil

from .file_type_base import FileType

class PDFf(FileType):
    
    def get_resume_str(self) -> str:
        pass  # FIX: to implement

    def post_llm_process(self, context, metadata=None) -> Path:
        # orig = Path(res_path)
        # timestamp = int(time.time())
        # working_copy = orig.with_name(f"{orig.stem}_{timestamp}{orig.suffix}")
        # shutil.copy2(orig, working_copy)
        raise NotImplementedError("PDF support is not yet implemented")  # FIX: to implement

