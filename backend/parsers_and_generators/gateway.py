import json
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from typing import Dict

from contracts import LLM_I, MOD_DEG, LLM_O
from LLM_CALL import CALL

from file_type_base import FileType
from file_type_docx import DOCXf
from file_type_txt import TXTf
from file_type_pdf import PDFf
from file_type_tex_j2 import J2f

GATEWAY_DIR         = Path(__file__).resolve().parent
RESUME_PATH         = (GATEWAY_DIR / '..' / 'templates' / 'resume' / 'BASE_RESUME_TEMPL.tex.j2').resolve()
PLACEHOLDERS_PATH   = (GATEWAY_DIR / '..' / 'fields.json').resolve()
JOB_POSTING_PATH    = (GATEWAY_DIR / '..' / 'postings_new' / 'job_posting_2.txt').resolve()
ACC_PATH            = (GATEWAY_DIR / '..' / 'resources' / 'ACC.txt').resolve()
SENSITIVE_PATH      = (GATEWAY_DIR / '..' / 'sensitive_fields.json').resolve()
OUTPUT_DIR          = (GATEWAY_DIR / '..' / 'outputs' ).resolve()

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
elif suffixes[-1] == '.txt':
    ft = TXTf()
elif suffixes[-1] == '.pdf':
    ft = PDFf()
else:
    raise ValueError("Resume file must be one of: .docx, .doc, .txt, .pdf, or .tex.j2")
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
llm_response:LLM_O  = CALL(payload)
mod_fields          = llm_response["placeholders"]
changes_made        = llm_response["changes_made"]
#print(f'placeholders = {mod_fields}')
print(f'changes_made = {changes_made}')

#Load context with sensitive data placeholders + new LLM-output field placeholders
context:Dict[str, str] = dict(sensitive_fields)
context.update(mod_fields)

ft.post_llm_process(RESUME_PATH, context, OUTPUT_DIR)
