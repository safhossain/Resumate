import os
import json
from pathlib import Path
import docx2txt
from docxtpl import DocxTemplate, RichText
from dotenv import load_dotenv, dotenv_values
from re import search

from models import LLM_I, MOD_DEG
from LLM_CALL import CALL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
#template_file_path = os.path.join(SCRIPT_DIR, '../templates/resume/BASE_RESUME_TEMPL_2.docx')
DOC_PATH = os.path.join(SCRIPT_DIR, 'test.docx')

ENV_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ENV_DIR / ".env"
load_dotenv(ENV_PATH)

env_keys = dotenv_values(ENV_PATH)
context = { key: os.getenv(key, "") for key in env_keys }

FIELDS_PATH = os.path.join(SCRIPT_DIR, '../fields.json')
with open(FIELDS_PATH) as f:
    fields = json.load(f)

context.update(fields)

doc = DocxTemplate(DOC_PATH)
doc.init_docx()

def render_fully(doc:DocxTemplate, context, max_passes=5):
    for i in range(max_passes):
        xml = doc.get_xml()
        if not search(r"{{\s*[^}]+\s*}}", xml):
            break
        doc.render(context)
        try:
            doc.save(str(DOC_PATH))
        except Exception as e:
            print("Save failed:", e)
        else:
            print(f"Saved -> {DOC_PATH}")
    else:
        raise RuntimeError("Too many nested rendering passes")

# try:
#     render_fully(doc, context)
# except Exception as e:
#     print("Render failed:", e)
# else:
#     print(f"Render good")

POSTING_PATH = os.path.join(SCRIPT_DIR, '../postings_new/job_posting_1.txt')

with open(POSTING_PATH, 'r', encoding='utf-8') as f:
    JOB_DESCRIPTION = f.read()

ACC_PATH = os.path.join(SCRIPT_DIR, '../resources/ACC.txt')
with open(ACC_PATH, 'r', encoding='utf-8') as f:
    ACC = f.read()

payload:LLM_I = {
    "full_resume": docx2txt.process(DOC_PATH),
    "placeholders": fields,
    "mod_deg": MOD_DEG.HIGH,
    "faux": True,
    "job_posting": JOB_DESCRIPTION,
    "acc": ACC
}

#print(str(payload))

LLM_O = CALL(payload)
print(LLM_O)