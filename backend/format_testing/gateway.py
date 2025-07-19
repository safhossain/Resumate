import os
import json
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

from docx_support import get_full_resume_from_docx, post_llm_process_docx
from models import LLM_I, MOD_DEG, LLM_O
from LLM_CALL import CALL

GATEWAY_DIR         = Path(__file__).resolve().parent
RESUME_PATH         = GATEWAY_DIR / 'test.docx'
PLACEHOLDERS_PATH   = (GATEWAY_DIR / '..' / 'fields.json').resolve()
JOB_POSTING_PATH    = (GATEWAY_DIR / '..' / 'postings_new' / 'job_posting_1.txt').resolve()
ACC_PATH            = (GATEWAY_DIR / '..' / 'resources' / 'ACC.txt').resolve()
ENV_PATH            = GATEWAY_DIR.parent / '.env'

with open(PLACEHOLDERS_PATH) as f:
    fields = json.load(f)
with open(JOB_POSTING_PATH, 'r', encoding='utf-8') as f:
    JOB_DESCRIPTION = f.read()
with open(ACC_PATH, 'r', encoding='utf-8') as f:
    ACC = f.read()

# get full resume in string form depending on file type
FULL_RESUME_STR = ""
RESUME_FILE_TYPE = RESUME_PATH.suffix.lower()
if RESUME_FILE_TYPE in {'.docx', 'doc'}:
    FULL_RESUME_STR = get_full_resume_from_docx(RESUME_PATH)
elif RESUME_FILE_TYPE == '.txt':
    with open(RESUME_PATH, 'r', encoding='utf-8') as f:
        FULL_RESUME_STR = f.read()
elif RESUME_FILE_TYPE == 'pdf':
    pass #process_pdf()
elif RESUME_FILE_TYPE == 'tex':
    pass #process_tex()
else:
    raise ValueError("Resume file needs to be one of .docx, doc, .txt, .pdf, or .tex")

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
#print(f'changes_made = {changes_made}')

# Load context with new LLM-output field placeholders + sensitive data .env placeholders
load_dotenv(ENV_PATH)
env_keys = dotenv_values(ENV_PATH)
context = { key: os.getenv(key, "") for key in env_keys }
context.update(mod_fields)

# process updating the respective documents' placeholders with new context
if RESUME_FILE_TYPE in {'.docx', '.doc'}:
    post_llm_process_docx(RESUME_PATH, context)
elif RESUME_FILE_TYPE == '.txt':    
    pass # post_llm_process_txt
elif RESUME_FILE_TYPE == '.pdf':
    pass # post_llm_process_pdf
elif RESUME_FILE_TYPE == '.tex':
    pass # post_llm_process_tex
else:
    raise ValueError("Resume file must be one of: .docx, .doc, .txt, .pdf, or .tex")
