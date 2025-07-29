from typing import Dict, Any, Optional
import re

''' 
NOTE: Everything in this file is LLM-generated becuase I don't know regex or escape keys
'''

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
def escape_latex(ctx: Any,
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
                   },
                   _LATEX_ESC_RE: re.Pattern = re.compile(
                       '(' + '|'.join(re.escape(c) for c in [
                           '\\', '&', '%', '$', '#', '_', '{', '}', '~', '^'
                       ]) + ')'
                   ))->Any:
    # Note: LLM-generated
    """
    Recursively walk ctx (which might be a dict, list, tuple or scalar).
    Any str gets latex-escaped; others are kept unchanged.
    """
    # 1) If this is a string, do a single-pass escape
    if isinstance(ctx, str):
        return _LATEX_ESC_RE.sub(lambda m: _LATEX_ESC[m.group(1)], ctx)

    # 2) If it's a dict, recurse on each value
    if isinstance(ctx, dict):
        return {k: escape_latex(v, _LATEX_ESC, _LATEX_ESC_RE)
                for k, v in ctx.items()}

    # 3) If it's a list or tuple, recurse in order
    if isinstance(ctx, list):
        return [escape_latex(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx]
    if isinstance(ctx, tuple):
        return tuple(escape_latex(v, _LATEX_ESC, _LATEX_ESC_RE) for v in ctx)

    # 4) Otherwise leave it alone (ints, None, etc.)
    return ctx

# xml escaping .....................................................
_XML_ESC: Dict[str, str] = {
    '&':  '&amp;',
    '<':  '&lt;',
    '>':  '&gt;',
}
_XML_ESC_RE = re.compile(
    '(' + '|'.join(re.escape(c) for c in _XML_ESC) + ')'
)

def escape_xml(ctx: Dict[str, str])-> Dict[str, str]:
    """
    Recursively escape XML special characters (& < > \" ') in strings within ctx.
    Supports dicts, lists, tuples, and scalar values.
    """
    # 1) If this is a string, do a single-pass XML escape
    if isinstance(ctx, str):
        return _XML_ESC_RE.sub(lambda m: _XML_ESC[m.group(1)], ctx)

    # 2) If it's a dict, recurse on each value
    if isinstance(ctx, dict):
        return {k: escape_xml(v) for k, v in ctx.items()}

    # 3) If it's a list or tuple, recurse in order
    if isinstance(ctx, list):
        return [escape_xml(v) for v in ctx]
    if isinstance(ctx, tuple):
        return tuple(escape_xml(v) for v in ctx)

    # 4) Otherwise leave it alone (ints, None, RichText objects, etc.)
    return ctx

def escape_chars(ctx: Dict[str, str], format:str)-> Dict[str, str]:
    print(format)  
    if format.endswith("tex") or format.endswith("tex.j2"):        
        return escape_latex(ctx)
    elif format.endswith("docx") or format.endswith("doc"):      
        return escape_xml(ctx)
    else:
        return ctx
