import os
import json
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

from models import LLM_I, MOD_DEG, LLM_O
from LLM_CALL import CALL

from file_type_base import FileType
from file_type_docx import DOCXf
from file_type_txt import TXTf
from file_type_pdf import PDFf
from file_type_tex import TEXf

GATEWAY_DIR         = Path(__file__).resolve().parent
RESUME_PATH         = (GATEWAY_DIR / '..' / 'templates' / 'resume' / 'BASE_RESUME_TEMPL.docx').resolve()
PLACEHOLDERS_PATH   = (GATEWAY_DIR / '..' / 'fields.json').resolve()
JOB_POSTING_PATH    = (GATEWAY_DIR / '..' / 'postings_new' / 'job_posting_1.txt').resolve()
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
RESUME_FILE_TYPE = RESUME_PATH.suffix.lower()
if RESUME_FILE_TYPE in {'.docx', 'doc'}:
    ft = DOCXf()
elif RESUME_FILE_TYPE == '.txt':
    ft = TXTf()
elif RESUME_FILE_TYPE == 'pdf':
    ft = PDFf()
elif RESUME_FILE_TYPE == 'tex':
    ft = TEXf()
else:
    raise ValueError("Resume file needs to be one of .docx, doc, .txt, .pdf, or .tex")
FULL_RESUME_STR = ft.get_full_resume(RESUME_PATH)

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

# Load context with sensitive data placeholders + new LLM-output field placeholders
context = dict(sensitive_fields)
context.update(mod_fields)

ft.post_llm_process(RESUME_PATH, context, OUTPUT_DIR)