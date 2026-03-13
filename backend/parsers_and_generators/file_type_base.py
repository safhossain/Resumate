from typing import Union, Optional, Dict
from abc import ABC, abstractmethod
from pathlib import Path
from os import PathLike


def build_output_tag(metadata: Optional[dict]) -> str:
    """Return the _model_posting_moddeg_faux segment for output filenames."""
    if not metadata:
        return ""
    model   = (metadata.get("model") or "NA").replace("/", "-")
    posting = Path(metadata.get("posting", "")).stem or "NA"
    moddeg  = metadata.get("moddeg", "NA")
    faux    = "faux" if metadata.get("faux") else "nofaux"
    return f"_{model}_{posting}_{moddeg}_{faux}"


class FileType(ABC):
    res_path: Path
    output_dir: Path
    context: Dict[str, str]
    dest_dir: Path

    def __init__(self, res_path: Union[str, PathLike], output_dir: Optional[Union[str, PathLike]] = None):
        self.res_path = Path(res_path)
        self.output_dir = Path(output_dir)
           
        if self.output_dir is not None:
            self.dest_dir = self.output_dir
        else:
            self.dest_dir = (self.res_path).parent     
        try:
            self.dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"destination folder dne: {e}")
        else:
            pass

    @abstractmethod
    def get_resume_str(self) -> str: ...

    @abstractmethod
    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None) -> None: ...
