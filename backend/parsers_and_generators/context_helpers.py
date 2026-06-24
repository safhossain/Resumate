from typing import Dict, Any, Callable, Optional
import re

''' 
NOTE: Everything in this file is LLM-generated becuase I don't know regex or escape keys
'''

# Matches any LaTeX control sequence: backslash followed by one or more letters.
# Presence of this in a value means the value is already LaTeX source and
# must not be run through escape_latex (escaping would mangle \href, \textbf, etc.)
_LATEX_CTRL_RE = re.compile(r'\\[a-zA-Z]')


def _deep_map(value: Any, transform: Callable[[str], str]) -> Any:
    """Recursively apply *transform* to every ``str`` inside *value*.

    Walks dicts, lists, and tuples; leaves non-string scalars (ints, None,
    RichText objects, etc.) untouched.
    """
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, dict):
        return {k: _deep_map(v, transform) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_map(v, transform) for v in value]
    if isinstance(value, tuple):
        return tuple(_deep_map(v, transform) for v in value)
    return value

def resolve_placeholders(ctx: Dict[str, Optional[str]], max_passes=5):
    # Note: LLM-generated
    """
    Repeatedly replace {{KEY}} in each ctx[value] with ctx[KEY], until
    no more changes occur (or max_passes is reached).
    """
    pattern = re.compile(r"{{\s*([\w]+)\s*}}")
    for _ in range(max_passes):
        changed = False
        for k, v in list(ctx.items()):
            if not isinstance(v, str):
                continue
            def repl(m):
                return ctx.get(m.group(1), "")
            new_v = pattern.sub(repl, v)
            if new_v != v:
                ctx[k] = new_v
                changed = True
        if not changed:
            break
    return ctx

# latex escaping .....................................................
_LATEX_ESC: Dict[str, str] = {
    '\\': r'\textbackslash{}',
    '&':  r'\&',
    '%':  r'\%',
    '$':  r'\$',
    '#':  r'\#',
    '_':  r'\_',
    '{':  r'\{',
    '}':  r'\}',
    '~':  r'\textasciitilde{}',
    '^':  r'\^{}',
}
_LATEX_ESC_RE = re.compile(
    '(' + '|'.join(re.escape(c) for c in ['\\', '&', '%', '$', '#', '_', '{', '}', '~', '^']) + ')'
)


def _escape_latex_str(s: str) -> str:
    # Skip values that already contain LaTeX control sequences (e.g. \href,
    # \textbf) — those values ARE LaTeX source and must not be mangled.
    if _LATEX_CTRL_RE.search(s):
        return s
    return _LATEX_ESC_RE.sub(lambda m: _LATEX_ESC[m.group(1)], s)


def escape_latex(ctx: Any) -> Any:
    """Recursively latex-escape every string in *ctx* (dict/list/tuple/scalar)."""
    return _deep_map(ctx, _escape_latex_str)

# xml escaping .....................................................
_XML_ESC: Dict[str, str] = {
    '&':  '&amp;',
    '<':  '&lt;',
    '>':  '&gt;',
}
_XML_ESC_RE = re.compile(
    '(' + '|'.join(re.escape(c) for c in _XML_ESC) + ')'
)


def _escape_xml_str(s: str) -> str:
    return _XML_ESC_RE.sub(lambda m: _XML_ESC[m.group(1)], s)


def escape_xml(ctx: Dict[str, str]) -> Dict[str, str]:
    """Recursively XML-escape (& < >) every string in *ctx*."""
    return _deep_map(ctx, _escape_xml_str)

def escape_chars(ctx: Dict[str, str], format:str)-> Dict[str, str]:
    if format.endswith("tex") or format.endswith("tex.j2"):        
        return escape_latex(ctx)
    elif format.endswith("docx") or format.endswith("doc"):      
        return escape_xml(ctx)
    else:
        return ctx
