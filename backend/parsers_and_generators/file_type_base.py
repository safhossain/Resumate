from typing import Union, Optional, Dict
from abc import ABC, abstractmethod
from pathlib import Path
from os import PathLike
import time


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

    def _build_output_path(self, metadata: Optional[dict], *, strip_last_suffix: bool = False) -> Path:
        """Compute the destination path for a rendered output.

        Produces ``<base><tag>_<timestamp><suffix><ext>`` under ``dest_dir``,
        where ``tag`` is the ``_model_posting_moddeg_faux`` segment, ``timestamp``
        and ``suffix`` come from *metadata* (shared across a run's retries), and
        ``ext`` is the template's full multi-suffix (e.g. ``.tex.j2``).

        ``strip_last_suffix=True`` drops the trailing template extension (e.g.
        ``.j2``) so a ``.tex.j2`` template yields a ``.tex`` working file.
        """
        orig = self.res_path
        meta = metadata or {}
        timestamp = meta.get("timestamp") or int(time.time())
        suffix = meta.get("suffix") or ""
        tag = build_output_tag(metadata)

        all_suffixes = "".join(orig.suffixes)
        if all_suffixes:
            base_name = orig.name[: -len(all_suffixes)]
            ext = all_suffixes
        else:
            base_name = orig.stem
            ext = orig.suffix

        name = f"{base_name}{tag}_{timestamp}{suffix}{ext}"
        if strip_last_suffix:
            name = Path(name).stem
        return self.dest_dir / name

    @abstractmethod
    def get_resume_str(self) -> str: ...

    @abstractmethod
    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None) -> Path: ...
