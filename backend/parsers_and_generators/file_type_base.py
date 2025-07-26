from abc import ABC, abstractmethod
from typing import Union, Optional, Dict
from os import PathLike

class FileType(ABC):
    @abstractmethod
    def get_resume_str(self, res_path:Union[str, PathLike])->str:
        pass
    @abstractmethod
    def post_llm_process(self, res_path: Union[str, PathLike], context: Dict[str, str], output_dir: Optional[Union[str, PathLike]] = None)->None:
        pass
