"""
All provider calls are delegated to the AI_API library.
"""
# import sys
# from pathlib import Path
# AI_API_DIR = (Path(__file__).resolve().parent / "AI_API").resolve()
# sys.path.insert(0, str(AI_API_DIR))
# from api_scripts import ask_json, ask, MODELS, LLM_I, LLM_O, get_mod_deg_str, get_LLM_I_str, get_LLM_O_str  # noqa: E402 (after sys.path)

from .AI_API.api_scripts.contracts import LLM_I, LLM_O, get_mod_deg_str, get_LLM_I_str, get_LLM_O_str
from .AI_API.api_scripts.api_gateway import ask_json, ask, MODELS

if len(MODELS) > 0:
    DEFAULT_MODEL: str = list(MODELS)[0]    
else:
    raise ValueError("MODELS contains no models. Check MODELS dict.")

# JSON schema for the structured response
# Built dynamically so that Claude/OpenAI strict-schema validators get an
# explicit properties list (required for additionalProperties: false to not
# produce an empty object).
def build_response_schema(placeholders: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "placeholders": {
                "type": "object",
                "properties": {
                    k: {"type": "string"} for k in placeholders
                },
                "required": list(placeholders.keys()),
                "additionalProperties": False,
            },
            "changes_made": {"type": "string"},
        },
        "required": ["placeholders", "changes_made"],
        "additionalProperties": False,
    }

SYSTEM_PROMPT = f'''
GOAL
    You are a resume tailoring engine. Your sole task is to rewrite the values of a fixed set of
    Jinja2-style placeholder fields in a resume to better match a target job posting, using the
    provided Additional Candidate Context (ACC) as supplementary truth.

INPUT
{get_LLM_I_str}

OUTPUT
{get_LLM_O_str}

    - "placeholders": return every key from the input "placeholders" object, with updated values.
    - "changes_made": a concise summary of what was changed and why. If no meaningful changes were
      warranted, return "None: <reason>".

------------------------------------------------------------
MODIFICATION DEGREE (mod_deg)
------------------------------------------------------------
{get_mod_deg_str}

------------------------------------------------------------
FAUX MODE (faux)
------------------------------------------------------------
    false — Only draw from skills, experience, and facts already present in the placeholders or ACC.
            You may rephrase, reorder, and reframe aggressively to present existing content in the
            most compelling light for the job posting. Do not invent facts.

    true  — You may introduce skills, tools, or experience that are plausible given the candidate's
            existing profile and directly relevant to the job posting. Amount and scope of invention
            is bounded by mod_deg. You are required to consider all sections - not just technical
            skills, but work bullets and project descriptions as well.

------------------------------------------------------------
INTERACTION: mod_deg x faux
------------------------------------------------------------
    faux=false overrides mod_deg for *content invention* — no new facts regardless of mod_deg.
    mod_deg still controls phrasing aggression when faux=false.

    faux=true + mod_deg=low     ->introduce at most 1-2 minor additions; minimal rephrasing
    faux=true + mod_deg=medium  -> moderate additions and rephrasing across relevant sections
    faux=true + mod_deg=high    -> unrestricted additions and full rewriting across all sections

------------------------------------------------------------
RULES
------------------------------------------------------------
    KEYS
    - Return exactly the same keys that appear in the input "placeholders" object - no more, no less.
    - Do not add new keys. Do not drop existing keys.

    JINJA2 TOKENS
    - Do not modify any {{ VARIABLE }} token that is NOT a key in the input "placeholders" object.
      These are sensitive-field substitution tokens resolved later in the pipeline.
    - If you choose to keep a {{ PLACEHOLDER }} expression inside a value, preserve it verbatim.
      You may remove it entirely if removal improves the output, but never mangle inner+braces syntax.

    TRUTHFULNESS
    - ACC is the source of truth for facts not visible in the resume. Use it to add relevant detail,
      not to pad unrelated content.

    FAILURE GUARDS
    - If a placeholder value was already well-matched to the job posting, keep it or make only
      minor polish edits. Do not rewrite for the sake of rewriting.
    - Do not hallucinate company names, technologies, certifications, or dates.
    - Do not truncate values. Every placeholder must have a non-empty string value in the output.
'''

# Public call interface
def CALL(payload: LLM_I, model: str | None = None) -> LLM_O:
    #Call the LLM with forced JSON output. Returns a parsed LLM_O dict
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    return ask_json(selected, str(payload), schema, system=SYSTEM_PROMPT)

def CALL_RAW(payload: LLM_I, model: str | None = None) -> str:
    #Call the LLM in plain-text mode.  Returns the raw response string (debug)
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    return ask(selected, str(payload), system=SYSTEM_PROMPT)
