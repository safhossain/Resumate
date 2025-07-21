from abc import ABC, abstractmethod
from typing import Union, Optional
from os import PathLike

class FileType(ABC):
    @abstractmethod
    def get_full_resume(self, path:str)->str:
        pass
    @abstractmethod
    def post_llm_process(self, res_path: Union[str, PathLike], context, output_dir: Optional[Union[str, PathLike]] = None)->None:
        pass
