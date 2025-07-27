from typing import Union, Optional, Dict
from pathlib import Path
from os import PathLike
import shutil
import time

from file_type_base import FileType
from jinja2_render import render_and_generate

class TXTf(FileType):    
    def get_resume_str(self, res_path:Union[str, PathLike])->str:
        with open(res_path, 'r', encoding='utf-8') as f:
            r = f.read()
        return r
    
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
        all_suffixes = "".join(orig.suffixes)
        base_name = orig.name[:-len(all_suffixes)] if all_suffixes else orig.stem
        new_name = Path(f"{base_name}_{timestamp}{all_suffixes}").stem
        working_copy = dest_dir / new_name
        shutil.copy2(orig, working_copy)

        render_and_generate(context, res_path, working_copy)
