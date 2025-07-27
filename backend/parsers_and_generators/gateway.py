from typing import Dict, Optional
from pathlib import Path
import argparse
import json
import re

from contracts import LLM_I, MOD_DEG, LLM_O
from LLM_CALL import CALL

from file_type_base import FileType
from file_type_docx import DOCXf
from file_type_txt_j2 import TXTf
from file_type_pdf import PDFf
from file_type_tex_j2 import J2f

GATEWAY_DIR         = Path(__file__).resolve().parent
RESUME_PATH         = (GATEWAY_DIR / '..' / 'templates' / 'resume' / 'BASE_RESUME_TEMPL.txt.j2').resolve()
PLACEHOLDERS_PATH   = (GATEWAY_DIR / '..' / 'fields.json').resolve()
JOB_POSTING_PATH    = (GATEWAY_DIR / '..' / 'postings_new' / 'job_posting_2.txt').resolve()
ACC_PATH            = (GATEWAY_DIR / '..' / 'resources' / 'ACC.txt').resolve()
SENSITIVE_PATH      = (GATEWAY_DIR / '..' / 'sensitive_fields.json').resolve()
OUTPUT_DIR          = (GATEWAY_DIR / '..' / 'outputs' ).resolve()

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

def main(opcode):
    with open(PLACEHOLDERS_PATH) as f:
        fields = json.load(f)
    with open(JOB_POSTING_PATH, 'r', encoding='utf-8') as f:
        JOB_DESCRIPTION = f.read()
    with open(ACC_PATH, 'r', encoding='utf-8') as f:
        ACC = f.read()
    with open(SENSITIVE_PATH) as f:
        sensitive_fields = json.load(f)

    # get full resume in string form depending on file type
    ft:FileType = None
    suffixes = [s.lower() for s in RESUME_PATH.suffixes]
    if suffixes[-2:] == ['.tex', '.j2']:
        ft = J2f()
    elif suffixes[-1] in {'.doc', '.docx'}:
        ft = DOCXf()
    elif suffixes[-2:] == ['.txt', '.j2']:
        ft = TXTf()
    elif suffixes[-1] == '.pdf':
        ft = PDFf()
    else:
        raise ValueError("Resume file must be one of: .docx, .doc, .txt.j2, .pdf, or .tex.j2")
    FULL_RESUME_STR = ft.get_resume_str(RESUME_PATH)

    #print(FULL_RESUME_STR)

    # Get LLM-modified field placeholders: file type agonstic
    payload:LLM_I = {
        "full_resume": FULL_RESUME_STR,
        "placeholders": fields,
        "mod_deg": MOD_DEG.HIGH,
        "faux": True,
        "job_posting": JOB_DESCRIPTION,
        "acc": ACC
    }
    if opcode != 1:
        llm_response: LLM_O = CALL(payload)
        mod_fields   = llm_response["placeholders"]
        changes_made = llm_response["changes_made"]
    else:
        mod_fields   = fields
        changes_made = "-"
    #print(f'placeholders = {mod_fields}')
    print(f'changes_made = {changes_made}')

    #Load context with sensitive data placeholders + new LLM-output field placeholders
    context:Dict[str, str] = dict(sensitive_fields)
    context.update(mod_fields)

    '''
        Warning: Recursive {{ PLACEHOLDERS }}

        If there are {{ PLACEHOLDERS }} in the fields dict's values, then they will 
        have to be PRE-rendered inside the `context` variable first. Why can't we 
        just continously render with jinja render() function? Because:
        Jinja2 rendering will cause all jinja-like blocks, such as {% ... %} and 
        {# ... #} to be "rendered away". So what we are left with is essentially RAW .tex
        Therefore, if you try to render twice, it will cause many TemplateSyntaxError 
        messages. There probably is a best-practices for multi-rendering, but in this 
        case, the easiest possible soln is just to simulate 'rendering' for the
        context dict which will feed into being an argument for jinja's render().
        This is done below with resolve_placeholders().
    '''
    context = resolve_placeholders(context)

    ft.post_llm_process(RESUME_PATH, context, OUTPUT_DIR)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Choose to make an LLM call or not"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-c", "--call",
        dest="do_call",
        action="store_true",
        help="Perform an LLM call"
    )
    group.add_argument(
        "-n", "--no",
        dest="do_call",
        action="store_false",
        help="LLM call NOT performed"
    )
    parser.set_defaults(do_call=True)
    args = parser.parse_args()
    if args.do_call:
        main(0)
    else:
        main(1)
