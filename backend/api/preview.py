"""Shared output-preview HTML rendering for the webapp routers."""

from __future__ import annotations

import html as html_mod
from pathlib import Path

import mammoth


def render_preview_html(output_path: Path, fmt: str) -> str:
    """Return an HTML preview of a rendered output file.

    docx -> mammoth HTML; txt -> escaped <pre>; tex/pdf -> download notice.
    """
    if fmt == "docx":
        with open(output_path, "rb") as fh:
            result = mammoth.convert_to_html(fh)
        return result.value
    if fmt == "txt":
        with open(output_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return f'<pre style="white-space:pre-wrap;">{html_mod.escape(text)}</pre>'
    return '<p class="text-gray-400">PDF generated — use the download button.</p>'
