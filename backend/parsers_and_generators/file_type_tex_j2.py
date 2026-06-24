from pathlib import Path
from typing import Dict, Optional
import re

from .file_type_base import FileType
from .jinja2_render import render_and_generate
from .context_helpers import escape_chars
from .brace_utils import brace_balance_errors
from .tex_to_pdf import gen_pdf
from ..constants import REMOVE_SENTINEL

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
        self.context = escape_chars(context, self.res_path.name)

        working_copy = self._build_output_path(metadata, strip_last_suffix=True)

        render_and_generate(self.context, self.res_path, working_copy)

        removed = _remove_sentinel_lines(working_copy)
        if removed:
            print(f"  LaTeX: removed {removed} REMOVE_BULLETPOINT sentinel(s) from .tex source")

        # Pre-flight brace check — surface a clear error before pdflatex sees it.
        tex_source = working_copy.read_text(encoding="utf-8")
        brace_errors = brace_balance_errors(tex_source)
        if brace_errors:
            summary = "; ".join(brace_errors[:3])
            if len(brace_errors) > 3:
                summary += f" (and {len(brace_errors) - 3} more)"
            raise RuntimeError(
                f"Rendered .tex has unbalanced braces — pdflatex will fail. "
                f"This is usually caused by a placeholder value that contains an extra '{{' or '}}'. "
                f"Details: {summary}"
            )

        pdf_path = gen_pdf(working_copy)
        return pdf_path
