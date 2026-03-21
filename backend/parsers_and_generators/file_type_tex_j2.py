from pathlib import Path
from typing import Dict, Optional
import re
import time

from .file_type_base import FileType, build_output_tag
from .jinja2_render import render_and_generate
from .tex_to_pdf import gen_pdf

REMOVE_SENTINEL = "REMOVE_BULLETPOINT"

_SENTINEL_RE = re.compile(
    r'\\resumeItem\s*\{' + re.escape(REMOVE_SENTINEL) + r'\}\s*\n?'
)


def _remove_sentinel_lines(tex_path: Path) -> int:
    """Remove \\resumeItem{REMOVE_BULLETPOINT} lines from the rendered .tex source."""
    content = tex_path.read_text(encoding="utf-8")
    cleaned, count = _SENTINEL_RE.subn('', content)
    if count:
        tex_path.write_text(cleaned, encoding="utf-8")
    return count


class J2f(FileType):

    def get_resume_str(self) -> str:
        with open(self.res_path, 'r', encoding='utf-8') as f:
            j2_str = f.read()
        return j2_str

    def post_llm_process(self, context: Dict[str, str], metadata: Optional[dict] = None) -> Path:
        self.context = context

        orig = self.res_path
        timestamp = (metadata.get("timestamp") if metadata else None) or int(time.time())
        suffix = (metadata.get("suffix") if metadata else None) or ""
        tag = build_output_tag(metadata)
        all_suffixes = "".join(orig.suffixes)
        base_name = orig.name[:-len(all_suffixes)] if all_suffixes else orig.stem
        new_name = Path(f"{base_name}{tag}_{timestamp}{suffix}{all_suffixes}").stem
        working_copy = self.dest_dir / new_name

        render_and_generate(self.context, self.res_path, working_copy)

        removed = _remove_sentinel_lines(working_copy)
        if removed:
            print(f"  LaTeX: removed {removed} REMOVE_BULLETPOINT sentinel(s) from .tex source")

        pdf_path = gen_pdf(working_copy)
        return pdf_path
