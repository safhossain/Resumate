"""Shared LaTeX brace-balance helpers.

Used by the .tex render pre-flight check and by the webapp placeholder
endpoints that warn about unbalanced selections.
"""

import re


def brace_balance(s: str) -> int:
    """Return the net brace depth of *s*.

    Positive = unclosed ``{`` group(s); negative = extra ``}``.
    """
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    return depth


def brace_balance_errors(tex_source: str) -> list[str]:
    """Return human-readable messages for every brace imbalance in *tex_source*.

    Scans line-by-line. An unmatched ``}`` is reported immediately; unclosed
    ``{`` groups are reported at end-of-file. Returns an empty list when braces
    balance. LaTeX comments (``%`` to end-of-line) are skipped.
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
