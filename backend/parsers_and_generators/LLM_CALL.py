"""
LLM call entrypoint.  All provider calls are delegated to the AI_API library
at backend/AI_API/python_llm_scripts.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

from contracts import LLM_I, LLM_O

# ── Bootstrap AI_API package ──────────────────────────────────────────────────
_AI_API_ROOT = (Path(__file__).resolve().parent.parent / "AI_API").resolve()
sys.path.insert(0, str(_AI_API_ROOT))

# Load keys from the .env that lives inside AI_API/
load_dotenv(_AI_API_ROOT / ".env")

from python_llm_scripts import ask_json, ask, MODELS  # noqa: E402  (after sys.path)

# public re-exports
DEFAULT_MODEL: str = "deepseek/chat"

# JSON schema for the structured response
# Built dynamically so that Claude/OpenAI strict-schema validators get an
# explicit properties list (required for additionalProperties: false to not
# produce an empty object).
def _build_response_schema(placeholders: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "placeholders": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in placeholders},
                "required": list(placeholders.keys()),
                "additionalProperties": False,
            },
            "changes_made": {"type": "string"},
        },
        "required": ["placeholders", "changes_made"],
        "additionalProperties": False,
    }

# System prompt
SYSTEM_PROMPT = '''
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
- Only modify the keys in the input "placeholders" object.
- Leave all other {{ VARIABLE }} tokens untouched for .env substitution.
- Preserve any nested {{ PLACEHOLDER }} expressions verbatim.
- Use ACC only when it adds relevant details to meet the job requirements.

IMPORTANT JSON RULES:
1. Output **only** valid, strict JSON (RFC 8259).
2. **Always** use double quotes (") for keys and string values.
3. **Never** use single quotes to delimit keys or values.
4. If a value contains a double quote, convert it to a single quote (\').
5. Do not include comments, trailing commas, or any non JSON syntax.
'''


# Public call interface

def CALL(payload: LLM_I, model: str | None = None) -> LLM_O:
    """Call the LLM with forced JSON output.  Returns a parsed LLM_O dict."""
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = _build_response_schema(payload["placeholders"])
    return ask_json(selected, str(payload), schema, system=SYSTEM_PROMPT)


def CALL_RAW(payload: LLM_I, model: str | None = None) -> str:
    """Call the LLM in plain-text mode.  Returns the raw response string (debug)."""
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    return ask(selected, str(payload), system=SYSTEM_PROMPT)
