from typing import Union, Optional
from pathlib import Path
from os import PathLike
import time
import shutil

from file_type_base import FileType

class PDFf(FileType):
    
    def get_resume_str(self, res_path: Union[str, PathLike])->str:
        pass #FIX: to implement
    
    def post_llm_process(self, res_path: Union[str, PathLike], context, output_dir: Optional[Union[str, PathLike]] = None)->None:
        orig = Path(res_path)
        timestamp = int(time.time())
        working_copy = orig.with_name(f"{orig.stem}_{timestamp}{orig.suffix}")
        shutil.copy2(orig, working_copy)
        pass #FIX: to implement

