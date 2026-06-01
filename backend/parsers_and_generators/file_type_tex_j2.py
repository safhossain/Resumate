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


def _brace_balance_errors(tex_source: str) -> list[str]:
    """Return human-readable messages for every brace imbalance found in *tex_source*.

    Scans line-by-line. An unmatched '}' is reported immediately; unclosed '{'
    groups are reported at end-of-file. Returns an empty list when braces balance.
    Comments (% to end-of-line) are skipped so they don't count.
    """
    errors: list[str] = []
    depth = 0
    for lineno, line in enumerate(tex_source.splitlines(), 1):
        # Strip LaTeX comments (% not preceded by \)
        stripped = re.sub(r'(?<!\\)%.*', '', line)
        for col, ch in enumerate(stripped, 1):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth < 0:
                    errors.append(f"Line {lineno}, col {col}: extra '}}' (no matching '{{')")
                    depth = 0  # reset and keep scanning for further issues
    if depth > 0:
        errors.append(f"End of file: {depth} unclosed '{{' group(s) remaining")
    return errors


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

        # Pre-flight brace check — surface a clear error before pdflatex sees it.
        tex_source = working_copy.read_text(encoding="utf-8")
        brace_errors = _brace_balance_errors(tex_source)
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
