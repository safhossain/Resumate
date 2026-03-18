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

_PAGE_HINT_SECTION = """
------------------------------------------------------------
PAGE TARGET
------------------------------------------------------------
    The rendered output must fit within {pages} page(s). Write concisely and precisely.
    Avoid padding, filler phrases, and redundancy.

    REMOVE_BULLETPOINT:
    - You may set any standalone bullet-point placeholder value to exactly: REMOVE_BULLETPOINT
    - The pipeline will physically delete that bullet/paragraph from the output.
    - Use this for content that is clearly off-topic for this job posting.
    - Do NOT use it for core identity fields (name, summary, contact info, headings).
"""

_RETRY_PAGE_SECTION = """
------------------------------------------------------------
PAGE CONSTRAINT RETRY  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    The rendered output was {actual_pages} page(s) — last page approximately {fill_pct_display}%
    filled — but the target is {target_pages} page(s).

    QUANTIFIED REDUCTION TARGET:
    - Current total placeholder chars : {total_chars}
    - Estimated chars to remove        : ~{chars_to_remove}
    - This is derived from the measured last-page fill percentage above.
    - Aim to cut at least {chars_to_remove} chars, prioritising the least job-relevant content.

    CONTENT REMOVAL IS ENCOURAGED:
    - Skills, tools, and experience bullet points that are NOT directly relevant to the job posting
      SHOULD be removed — do not keep them just to fill space.
    - When mod_deg is medium-low, medium, medium-high, or high, feel free to cut entire bullets or
      skill items that add little value for this specific role.
    - When faux=true and mod_deg is medium-low, medium, medium-high, or high, you MAY replace
      removed content with tighter, more relevant content — but only if it fits within the page target.

    REMOVE_BULLETPOINT SENTINEL:
    - To signal that an entire bullet point or paragraph should be physically deleted from the
      document, set the placeholder value to exactly the string: REMOVE_BULLETPOINT
    - The pipeline will detect this sentinel and remove the whole paragraph/bullet from the output.
    - Use REMOVE_BULLETPOINT for standalone bullet-point placeholders that represent discrete items
      (e.g. a single experience bullet, a skill line). Do NOT use it for core identity fields such
      as name, summary, job title, contact info, or section headings.
    - Prefer REMOVE_BULLETPOINT over leaving a short, filler-filled value.

    CONDENSING STRATEGY (apply in this order):
    1. REMOVE_BULLETPOINT on the least job-relevant bullet points / skill items.
    2. Shorten remaining bullets — cut filler phrases, tighten wording.
    3. Condense verbose sentences without losing key information.
    4. As a last resort, merge two closely related bullet points into one.

    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it as above).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""

# Public call interface
def CALL(payload: LLM_I, model: str | None = None, page_hint: int | None = None) -> LLM_O:
    """Call the LLM with forced JSON output. Returns a parsed LLM_O dict.

    page_hint: if set, appends a concise page-target section to the system prompt
    and enables the REMOVE_BULLETPOINT sentinel for the initial call.
    """
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    system = SYSTEM_PROMPT
    if page_hint is not None:
        system = system + _PAGE_HINT_SECTION.format(pages=page_hint)
    return ask_json(selected, str(payload), schema, system=system)

def CALL_RETRY(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    chars_to_remove: int,
    last_page_fill_pct: float,
    model: str | None = None,
) -> LLM_O:
    """Second LLM call issued when the rendered output exceeded the page target.

    *payload* should contain the LLM-modified placeholders from the first call
    (not the originals) so the model can see what it already produced and trim from there.
    """
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    mod_deg = payload.get("mod_deg")
    mod_deg_val = mod_deg.value if hasattr(mod_deg, "value") else str(mod_deg)
    total_chars = sum(len(v) for v in payload["placeholders"].values())
    retry_system = SYSTEM_PROMPT + _RETRY_PAGE_SECTION.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        total_chars=total_chars,
        chars_to_remove=chars_to_remove,
    )
    return ask_json(selected, str(payload), schema, system=retry_system)

_SECOND_RETRY_SECTION = """
------------------------------------------------------------
SECOND RETRY — WIDOW LINE TARGETING  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    After the first retry, the output is still {actual_pages} page(s) with the last page
    {fill_pct_display}% filled (target: {target_pages} page(s)).
    Estimated chars still to remove: ~{chars_to_remove}.

    PRIMARY TECHNIQUE — REPHRASE WIDOW LINES (do this first):
    The following placeholders have been identified as having "widow" last lines in the rendered
    output — their final rendered line contains only a few words. Rephrasing them to be 1 line
    shorter can reclaim the needed space WITHOUT removing any skills, technologies, or facts.

    Widow line targets:
{widow_lines_block}
    For each of these targets:
    - Rephrase so the value fits in 1 fewer rendered line.
    - Prefer: tighter phrasing, removing filler words, combining clauses.
    - Small substitutions like "using" → "via", "in order to" → "to" help.
    - Do NOT remove skills, technologies, metrics, or factual content from these values.
    - If after rephrasing a value becomes too short to stand alone, use REMOVE_BULLETPOINT instead.

    IMPORTANT — ROLE NAMES, TITLES, AND LABELS:
    If a widow target appears to be a role name, job title, position label, company name, date
    range, section label, or any other short identity/metadata field (e.g. "w2_role", "p2_desc"
    style keys, or values that are just a job title like "Senior Software Engineer"), treat it
    differently:
    - Do NOT rephrase or shorten it aggressively — role names and titles must remain accurate.
    - At most, make a very minor cosmetic tweak (e.g. remove a redundant word) if one is
      completely obvious and harmless; otherwise leave the value unchanged.
    - Instead, redirect effort to the secondary technique (REMOVE_BULLETPOINT or condensing
      on nearby bullet points).

    SECONDARY TECHNIQUE — only if widow rephrasing alone is insufficient:
    Apply REMOVE_BULLETPOINT or further condensing on the least-relevant remaining bullets
    (same rules as before).

    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""


def CALL_RETRY2(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    chars_to_remove: int,
    last_page_fill_pct: float,
    widow_lines: dict,
    model: str | None = None,
) -> LLM_O:
    """Third LLM call (user-prompted) — targets widow lines for 1-line rephrasing
    before falling back to content removal.

    *payload* should contain the placeholders from the first retry so the model
    sees the current state and can apply targeted widow rephrasing.
    """
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    mod_deg = payload.get("mod_deg")
    mod_deg_val = mod_deg.value if hasattr(mod_deg, "value") else str(mod_deg)

    if widow_lines:
        lines = []
        for key, value in widow_lines.items():
            display = value[:120] + "..." if len(value) > 120 else value
            lines.append(f'    - {key}: "{display}"')
        widow_lines_block = "\n".join(lines)
    else:
        widow_lines_block = "    (none detected — fall back to secondary technique)"

    total_chars = sum(len(v) for v in payload["placeholders"].values())
    second_retry_system = SYSTEM_PROMPT + _SECOND_RETRY_SECTION.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        chars_to_remove=chars_to_remove,
        widow_lines_block=widow_lines_block,
    )
    return ask_json(selected, str(payload), schema, system=second_retry_system)


def CALL_RAW(payload: LLM_I, model: str | None = None) -> str:
    #Call the LLM in plain-text mode.  Returns the raw response string (debug)
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    return ask(selected, str(payload), system=SYSTEM_PROMPT)
