from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import json
import os

from contracts import LLM_I, LLM_O

ENV_DIR = Path(__file__).resolve().parent
ENV_PATH = ENV_DIR / ".env"
load_dotenv(ENV_PATH)
API_KEY = os.getenv('DEEPSEEK_KEY')

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

SYSTEM_PROMPT0 = '''
                GOAL: Modify (as necessary) a current Resume's placeholders (which User will provide) based on a job posting description, and 'Additional Candidate Context (ACC)' (all User-provided).
                The Resume will be filled with Jinja2-like placeholder fields. Some will be related to sensitive information which will be manually updated
                via .env substition post-API call. Others will be considered 'fields' which will be the ONLY sections being updated by this LLM call. 
                
                You will be provided a JSON-like input:
                payload:LLM_I = {
                    "full_resume": str
                    "placeholders": dict,
                    "mod_deg": MOD_DEG
                    "faux": bool,
                    "job_posting": str,
                    "acc": str
                }

                where MOD_DEG is derived from:              
                ```
                class MOD_DEG(Enum):
                    LOW = "low"
                    MEDIUM = "medium"
                    HIGH = "high"
                ```                

                Your final goal would be to return a JSON-like Output that modifies the original 'placeholder' field, 
                as well as a summary of changes made (or state "None" and state briefly why no changes required) in the changes_made field:
                {
                    "placeholders": dict-like,
                    "changes_made" : str
                }                
                
                You do not need to treat the ACC as a high level priority resource to utilize unless it would truly be relevant to the job posting.

                The user will also provide a level of 'degree' of modification required. This param will be known as 'mod_deg':
                - LOW: No phrasing changes, but can add specific skill(s) that aren't already present in fields placeholders based on requirements from job posting. May remove at most 1-2 mentioned skills if deemed as a negative respective to the job posting.
                - MEDIUM: Can slightly modify of certain field placeholders. May add/remove skill(s) as deemed necessary based on job posting requirements
                - HIGH: Can modify phrasing/skillset as much as deemed necessary based on job posting requirements
                
                Additionally, there will be a parameter for whether or not a User would want modifictions using skills that the User does not have.
                That param will be called 'faux' (boolean True or False).

                Examples if ...
                    Premise: Job Posting requires 'Machine Learning' but User's current Resume and the ACC does not have any skills relating to 'ML'
                
                a) faux is False (default):
                    Action: You will modify (according to mod_deg) to match job posting's requirement of ML as much as possible, but only with the skills/experience (or adjacent skills/exp) given in User's Resume and ACC

                b) faux is True:                     
                    Action: You may add NEW (ex: ML-related) skills/re-phrasing (level of modification once again dependent on mod_deg) which are NOT present from User Resume/ACC.
                    Additional mod_deg info:
                        LOW: Only technical skills addition/subtraction (ex: add ML-related skills but not experience)
                        MEDIUM: Along with LOW modification, can modify EXISTING experience to be closer to (ex: ML-related) requirements
                        HIGH: along with LOW+MEDIUM modifiction, add NEW generic (ex: ML-related) experience one could expect a candidate to have based on the job posting requirements

                Once again, the "fields" placeholders in the Resume will be the ONLY sections being modified (regardless of the values of mod_deg or faux). They will
                may like {{ languages_section }} or {{ w1_b1 }} in the Resume itself, and all the required fields WILL BE PROVIDED in the user prompt looking like example below:
                {
                    "languages_section":"Python, JavaScript, Java, C++, Go, Ruby, Rust",
                    "frameworks_section":"React, Django, Flask, Angular, Spring, Express, TensorFlow, NumPy, Docker, Kubernetes, AWS, Azure, Git, Linux, Node.js, Firebase",
                    "w1_b1": "Developed and maintained scalable web applications using React and Node.js, integrating RESTful APIs and optimizing performance across various environments."
                }

                Any other placeholders that look like {{ VARIABLE }} -but which are not mentioned in the required fields JSON- are .env variables that 
                are meant for post-LLM call modification and not to be modified by the call.

                Note: if there are {{ VARIABLE }} placeholders inside the fields themselves, keep it verbatum (given that mod_deg and faux deems it necessary to keep).
                Example:
                {
                ...,
                "w4_b1": "Successfully launched the {{ SCHOOL_ABBR_NAME }} Chapter of {{ CLUB2_NAME }}, created the annual budget, and actively manage allocations for each project, ensuring financial efficiency and adaptability throughout the school year."
                }

                So if and only if after accounting for mod_deg and faux parameters that we find that the above placeholders {{ SCHOOL_ABBR_NAME }} and
                {{ CLUB2_NAME }} remains, then keep it EXACTLY like that as they will be post-processed later.
                '''

SYSTEM_PROMPT_1 = '''
GOAL
    Update a resume's Jinja2-style placeholders based on a job posting and Additional Candidate Context (ACC).

INPUT (payload:LLM_I)
{
    "full_resume": str,
    "placeholders": dict,        # only these keys will be modified
    "mod_deg": "low"|"medium"|"high",
    "faux": bool,
    "job_posting": str,
    "acc": str
}

MOD_DEG
    "low"    - no phrasing changes; may add up to 2 missing skills from the job posting; may remove up to 2 conflicting skills
    "medium" - minor phrasing edits; add or remove skills as needed
    "high"   - unrestricted phrasing and skill adjustments

FAUX
    false - restrict additions/edits to skills and experience already in placeholders or ACC
    true  - introduce new skills or experience implied by the job posting, amount is subject to mod_deg value; you should try to update not just for technical skills but possibly (if viable) Project and Work sections

OUTPUT
Return exactly:
{
    "placeholders": dict,    # updated values for each provided key
    "changes_made": str      # summary of edits or "None: <reason>"
}

RULES
- Only modify the keys in the input “placeholders” object.
- Leave all other {{ VARIABLE }} tokens untouched for .env substitution.
- Preserve any nested {{ PLACEHOLDER }} expressions verbatim.
- Use ACC only when it adds relevant details to meet the job requirements.

IMPORTANT JSON RULES:
1. Output **only** valid, strict JSON (RFC 8259).
2. **Always** use double quotes (") for keys and string values.
3. **Never** use single quotes to delimit keys or values.
4. If a value contains a double quote, convert it to a single quote (').
5. Do not include comments, trailing commas, or any non JSON syntax.
'''

############################

def CALL(payload: LLM_I)->LLM_O:
    USER_PROMPT = str(payload)

    MESSAGES = [{"role": "system", "content": SYSTEM_PROMPT_1},
                {"role": "user", "content": USER_PROMPT}]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=MESSAGES,
        stream=False,
        response_format={
            'type': 'json_object'
        }    
    )

    RESPONSE:str = response.choices[0].message.content
    #print(f"*-*-*-*-*-*-*-*-\n{RESPONSE}\n*-*-*-*-*-*-*-*-")

    return json.loads(RESPONSE)
