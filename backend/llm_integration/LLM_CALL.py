"""
All provider calls are delegated to the AI_API library.
"""

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
    - "changes_made": a numbered list, one entry per placeholder key, in the format:
        1. key_name: <what changed and why>
        2. key_name: NONE
      Include every key that was changed with a brief reason. For keys left unchanged, write NONE.
      If no placeholder was changed at all, write a single line: "No changes were made: <reason>".

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
    - Do not modify any {{{{ VARIABLE }}}} token that is NOT a key in the input "placeholders" object.
      These are sensitive-field substitution tokens resolved later in the pipeline.
    - If you choose to keep a {{{{ PLACEHOLDER }}}} expression inside a value, preserve it verbatim.
      You may remove it entirely if removal improves the output, but never mangle inner+braces syntax.

    TRUTHFULNESS
    - ACC is the source of truth for facts not visible in the resume. Use it to add relevant detail,
      not to pad unrelated content.

    SKILL SECTIONS — BALANCE ADDITIONS WITH REMOVALS
    - When you add new skills, tools, or technologies to a skills-type placeholder, you are equally
      required to remove existing entries that are less relevant to the job posting.
    - Rule of thumb: for every 3 or more new items added to a single skills placeholder, drop at
      least 1 existing item from that same placeholder — the one least relevant to the posting.
    - The goal is a tightly curated list that signals fit, not a padded "I know everything" list.
      A shorter, sharper skills section is more compelling than a long one diluted with tangential tools.
    - Entries to consider removing first: tools from domains unrelated to the posting, learning/hobby
      frameworks that aren't used professionally in this role, older or niche technologies that add
      no signal for this specific job.
    - This applies even at faux=false — you are always allowed (and expected) to remove existing
      entries when enough new, more-relevant ones are introduced.

    TYPOGRAPHY (all placeholder values and changes_made)
    - Do not use em dashes (U+2014), en dashes (U+2013), figure dashes, horizontal bars (U+2015),
      or any other long or fancy Unicode hyphen/dash characters. Use a normal ASCII hyphen-minus (-),
      commas, semicolons, or parentheses to separate clauses instead.
    - Do not include emojis, emoticons, or kaomoji-style text faces in any placeholder value or in
      changes_made.

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

_BASELINE_METRICS_SECTION = """
------------------------------------------------------------
BASELINE RENDER METRICS  (from rendering the ORIGINAL placeholders)
------------------------------------------------------------
    The resume was rendered with the original (pre-tailoring) placeholder values.
    Below are the character counts per placeholder AS THEY FIT on the page today.
    Your tailored values should stay within these bounds — do NOT inflate content.

    CHAR BUDGETS PER PLACEHOLDER:
{char_budget_lines}
    ────────────────────
    TOTAL: {total_chars} chars across {placeholder_count} placeholders

    WARNING: If your tailored output significantly exceeds a placeholder's original char count,
    it will push the resume past the page target. Match or shorten — do not bloat.
"""


# ---------------------------------------------------------------------------
# Shared sections used across all retry prompts
# ---------------------------------------------------------------------------

_DO_NOT_MODIFY_SECTION = """
    DO NOT MODIFY — even if they appear as MBP targets:
    - Role names / job titles (e.g. keys containing "_role")
    - URLs (e.g. keys containing "_url")
    Keep these values exactly as-is. Redirect effort to other placeholders.
"""


def _format_mbp_analysis(mbp_analysis=None) -> str:
    """Build the MBP analysis block for insertion into retry prompts.

    *mbp_analysis* should be an MbpAnalysis from visual_lines.analyze_mbps.
    Returns an empty string if no analysis is available.
    """
    if mbp_analysis is None:
        return ""

    avg_b = mbp_analysis.avg_chars_per_bullet_line
    avg_p = mbp_analysis.avg_chars_per_para_line
    last_pg_lines = mbp_analysis.lines_on_last_page

    tier_a = mbp_analysis.tier_a
    tier_b = mbp_analysis.tier_b
    tier_c = mbp_analysis.tier_c

    parts = [
        "",
        "    ══════════════════════════════════════════════════════════════",
        "    RENDERED LINE METRICS  (measured from actual PDF output)",
        "    ══════════════════════════════════════════════════════════════",
        f"      Max chars on 1 bullet line  : ~{avg_b:.0f}",
        f"      Max chars on 1 paragraph line: ~{avg_p:.0f}",
        f"      Visual lines on LAST page    : {last_pg_lines}",
        "",
        "    ── RULE: HOW LINE SAVINGS WORK ──",
        "      To save 1 visual line you MUST do ONE of:",
        "        (a) Shorten a multi-line element so it fits on FEWER lines.",
        "            That means the ENTIRE value must be ≤ the 1-line capacity shown below.",
        "        (b) Set a bullet/paragraph to REMOVE_BULLETPOINT (deletes it entirely).",
        "      ⚠ Trimming a few words while the element STILL wraps to the same",
        "        number of lines saves ZERO space. Do NOT waste edits on partial trims.",
    ]

    def _fmt_target(d, tier_label):
        """Format one MBP target with prominent last-line words."""
        last_text = d.last_line_text.strip()
        if len(last_text) > 100:
            last_text = last_text[:97] + "..."
        lines = [
            f"      ┌─ {d.key}  ({d.kind}, {tier_label})",
            f"      │  Current length : {d.total_chars} chars → renders as {d.visual_line_count} visual lines",
            f"      │  1-line capacity: ≤ {d.one_line_cap} chars  →  you must CUT ≥ {d.chars_over} chars",
            f"      │",
            f"      │  OVERFLOW WORDS (the last rendered line — these are the words that",
            f"      │  push this element onto an extra line. Remove/absorb them):",
            f'      │    >>> "{last_text}"',
            f"      └────",
        ]
        return lines

    if tier_a:
        parts.append("")
        parts.append("    ── TIER A — EASY WINS  (last line barely filled) ──")
        parts.append("    Rephrase to ≤ the 1-line capacity. These are the lowest-hanging fruit.")
        for d in tier_a:
            parts.extend(_fmt_target(d, "Tier A"))

    if tier_b:
        parts.append("")
        parts.append("    ── TIER B — MODERATE EFFORT  (needs aggressive rewrite) ──")
        parts.append("    Rephrase down to ≤ the 1-line capacity, or use REMOVE_BULLETPOINT.")
        for d in tier_b:
            parts.extend(_fmt_target(d, "Tier B"))

    if tier_c:
        parts.append("")
        parts.append(
            f"    ── TIER C — ALREADY TIGHT  ({len(tier_c)} element(s)) ──"
        )
        parts.append(
            "    Rephrasing won't save a line here. "
            "Use REMOVE_BULLETPOINT on these only if more space is still needed."
        )

    if not tier_a and not tier_b:
        parts.append("")
        parts.append(
            "    (No rephrasing targets — all multi-line elements have full last lines.)"
        )

    # Line budget
    a_saves = len(tier_a)
    b_saves = len(tier_b)
    total_saves = a_saves + b_saves

    parts.append("")
    parts.append("    ══════════════════════════════════════════════════════════════")
    parts.append("    LINE BUDGET")
    parts.append("    ══════════════════════════════════════════════════════════════")
    parts.append(f"      Lines to free to hit page target: {last_pg_lines}")
    if tier_a:
        parts.append(f"      Tier A rephrasing can save up to : {a_saves} line(s)")
    if tier_b:
        parts.append(f"      Tier B rephrasing can save up to : {b_saves} line(s)")
    parts.append(f"      Each REMOVE_BULLETPOINT on a 2-line element saves 2 lines.")
    parts.append(f"      Each REMOVE_BULLETPOINT on a 1-line element saves 1 line.")

    if total_saves >= last_pg_lines:
        parts.append("")
        parts.append(
            f"      → Shortening {last_pg_lines} of the Tier A/B targets "
            "to 1-line SHOULD be enough."
        )
    else:
        deficit = last_pg_lines - total_saves
        parts.append("")
        parts.append(
            f"      → Rephrasing all Tier A+B saves ~{total_saves} lines, "
            f"which is NOT enough."
        )
        parts.append(
            f"      → You MUST also use REMOVE_BULLETPOINT on at least "
            f"{(deficit + 1) // 2} two-line element(s) "
            f"(or {deficit} one-line elements) to close the gap."
        )
        parts.append(
            "      → Pick the LEAST important bullets for removal."
        )

    parts.append("    ══════════════════════════════════════════════════════════════")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# DOCX retry prompts
# ---------------------------------------------------------------------------

_RETRY_PAGE_SECTION = """
------------------------------------------------------------
PAGE CONSTRAINT RETRY  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    The rendered output was {actual_pages} page(s) — last page approximately {fill_pct_display}%
    filled — but the target is {target_pages} page(s).

{mbp_block}
    STRATEGY — SAVE RENDERED LINES (apply in this order):

    1. For each Tier A target listed above:
       - Look at the "OVERFLOW WORDS" — these are the exact words that push the element
         onto an extra rendered line.
       - Rewrite the ENTIRE value so it fits within the "1-line capacity" char limit.
         That means the whole value, not just the end. Tighten throughout: use shorter
         synonyms, drop filler words, merge clauses.
       - If trimming to fit is impossible, set the value to REMOVE_BULLETPOINT.
       - ⚠ Trimming a few words while the value is STILL over the 1-line capacity
         saves ZERO visual lines. You must reach the limit or it changes nothing.

    2. If Tier A alone is not enough (see LINE BUDGET), do the same for Tier B targets.

    3. REMOVE_BULLETPOINT: set any standalone bullet/paragraph placeholder value to exactly
       the string REMOVE_BULLETPOINT to physically delete it from the output.
       Use this for items NOT directly relevant to the job posting.
       Do NOT use it for core identity fields (name, summary, contact info, headings).
       A REMOVE_BULLETPOINT on a 2-line element saves 2 lines; on a 1-line saves 1 line.

    4. Last resort: condense verbose sentences, merge closely related elements.

    CONTENT REMOVAL IS ENCOURAGED when mod_deg is medium or higher — do not keep
    off-topic bullets just to fill space. Prefer REMOVE_BULLETPOINT over filler.
""" + _DO_NOT_MODIFY_SECTION + """
    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it as above).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""


_SECOND_RETRY_SECTION = """
------------------------------------------------------------
SECOND RETRY — MBP TARGETED REPHRASING  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    After the first retry, the output is still {actual_pages} page(s) with the last page
    {fill_pct_display}% filled (target: {target_pages} page(s)).

{mbp_block}
    INSTRUCTIONS (follow EXACTLY):

    For each Tier A and Tier B target above:
    1. Read the "OVERFLOW WORDS" — those are the exact rendered words causing the extra line.
    2. Read the "1-line capacity" — that is the MAXIMUM char count for the value to fit on
       one rendered line.
    3. Rewrite the ENTIRE VALUE to be ≤ that char limit. Not just the end — tighten the
       whole sentence. Use shorter words, cut qualifiers, merge clauses.
    4. Count the chars of your new value. If it is STILL over the limit, shorten further
       or set the value to REMOVE_BULLETPOINT.
    5. ⚠ ANY value that stays over the 1-line capacity will still wrap to 2 lines,
       saving ZERO space. Partial shortening is USELESS.

    If the LINE BUDGET says rephrasing is not enough, you MUST use REMOVE_BULLETPOINT
    on the least important bullets/paragraphs until the budget is met.
""" + _DO_NOT_MODIFY_SECTION + """
    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""


# ---------------------------------------------------------------------------
# Public call interface — DOCX
# ---------------------------------------------------------------------------

def _format_baseline_metrics(original_fields: dict | None) -> str:
    """Build the baseline char-budget block from original placeholder values."""
    if not original_fields:
        return ""
    sorted_items = sorted(original_fields.items(), key=lambda kv: len(kv[1]), reverse=True)
    total = sum(len(v) for v in original_fields.values())
    width = max((len(k) for k in original_fields), default=10)
    lines = []
    for k, v in sorted_items:
        lines.append(f"      {k:<{width}}  {len(v):>4} chars")
    return _BASELINE_METRICS_SECTION.format(
        char_budget_lines="\n".join(lines),
        total_chars=total,
        placeholder_count=len(original_fields),
    )


def CALL(
    payload: LLM_I,
    model: str | None = None,
    page_hint: int | None = None,
    baseline_fields: dict | None = None,
) -> LLM_O:
    """Call the LLM with forced JSON output. Returns a parsed LLM_O dict.

    page_hint: if set, appends a concise page-target section to the system prompt
    and enables the REMOVE_BULLETPOINT sentinel for the initial call.
    baseline_fields: if set, appends per-placeholder char budgets from the
    pre-render to help the LLM stay within page bounds on the first try.
    """
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    system = SYSTEM_PROMPT
    if page_hint is not None:
        system = system + _PAGE_HINT_SECTION.format(pages=page_hint)
    if baseline_fields is not None:
        system = system + _format_baseline_metrics(baseline_fields)
    return ask_json(selected, str(payload), schema, system=system)


def CALL_RETRY(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    last_page_fill_pct: float,
    mbp_analysis=None,
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
    mbp_block = _format_mbp_analysis(mbp_analysis)
    retry_system = SYSTEM_PROMPT + _RETRY_PAGE_SECTION.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        mbp_block=mbp_block,
    )
    return ask_json(selected, str(payload), schema, system=retry_system)


def CALL_RETRY2(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    last_page_fill_pct: float,
    mbp_analysis=None,
    model: str | None = None,
) -> LLM_O:
    """Third LLM call (user-prompted) — targets MBP rephrasing for 1-line savings
    before falling back to content removal.

    *payload* should contain the placeholders from the first retry so the model
    sees the current state and can apply targeted MBP rephrasing.
    """
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    schema = build_response_schema(payload["placeholders"])
    mod_deg = payload.get("mod_deg")
    mod_deg_val = mod_deg.value if hasattr(mod_deg, "value") else str(mod_deg)
    mbp_block = _format_mbp_analysis(mbp_analysis)
    second_retry_system = SYSTEM_PROMPT + _SECOND_RETRY_SECTION.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        mbp_block=mbp_block,
    )
    return ask_json(selected, str(payload), schema, system=second_retry_system)


# ---------------------------------------------------------------------------
# LaTeX-specific addendum and prompts
# ---------------------------------------------------------------------------

_RETRY_PAGE_SECTION_TEX = """
------------------------------------------------------------
PAGE CONSTRAINT RETRY — LaTeX  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    The rendered PDF was {actual_pages} page(s) — last page approximately {fill_pct_display}%
    filled — but the target is {target_pages} page(s).

{mbp_block}
    STRATEGY — SAVE RENDERED LINES (apply in this order):

    1. For each Tier A target listed above:
       - Look at the "OVERFLOW WORDS" — these are the exact words that push the element
         onto an extra rendered line.
       - Rewrite the ENTIRE value so it fits within the "1-line capacity" char limit.
         That means the whole value, not just the end. Tighten throughout: use shorter
         synonyms, drop filler words, merge clauses.
       - If trimming to fit is impossible, set the value to REMOVE_BULLETPOINT.
       - ⚠ Trimming a few words while the value is STILL over the 1-line capacity
         saves ZERO visual lines. You must reach the limit or it changes nothing.

    2. If Tier A alone is not enough (see LINE BUDGET), do the same for Tier B targets.

    3. REMOVE_BULLETPOINT: set any standalone bullet/paragraph placeholder value to exactly
       the string REMOVE_BULLETPOINT to physically delete that \\resumeItem from the .tex.
       Use this for items NOT directly relevant to the job posting.
       Do NOT use it for core identity fields (name, summary, contact info, headings).
       A REMOVE_BULLETPOINT on a 2-line element saves 2 lines; on a 1-line saves 1 line.

    4. Last resort: condense verbose sentences, merge closely related elements.

    CONTENT REMOVAL IS ENCOURAGED when mod_deg is medium or higher — do not keep
    off-topic bullets just to fill space. Prefer REMOVE_BULLETPOINT over filler.

    NO LATEX COMMANDS IN VALUES:
    - Do NOT include \\vspace, \\setlength, \\renewcommand, or any other LaTeX commands
      in placeholder values. Return plain text content only.
""" + _DO_NOT_MODIFY_SECTION + """
    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it as above).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""


_SECOND_RETRY_SECTION_TEX = """
------------------------------------------------------------
SECOND RETRY — MBP TARGETED REPHRASING, LaTeX  (mod_deg={mod_deg}, faux={faux})
------------------------------------------------------------
    After the first retry, the rendered PDF is still {actual_pages} page(s) with the last page
    {fill_pct_display}% filled (target: {target_pages} page(s)).

{mbp_block}
    INSTRUCTIONS (follow EXACTLY):

    For each Tier A and Tier B target above:
    1. Read the "OVERFLOW WORDS" — those are the exact rendered words causing the extra line.
    2. Read the "1-line capacity" — that is the MAXIMUM char count for the value to fit on
       one rendered line.
    3. Rewrite the ENTIRE VALUE to be ≤ that char limit. Not just the end — tighten the
       whole sentence. Use shorter words, cut qualifiers, merge clauses.
    4. Count the chars of your new value. If it is STILL over the limit, shorten further
       or set the value to REMOVE_BULLETPOINT.
    5. ⚠ ANY value that stays over the 1-line capacity will still wrap to 2 lines,
       saving ZERO space. Partial shortening is USELESS.

    If the LINE BUDGET says rephrasing is not enough, you MUST use REMOVE_BULLETPOINT
    on the least important bullets/paragraphs until the budget is met.

    NO LATEX COMMANDS IN VALUES:
    - Do NOT include \\vspace, \\setlength, \\renewcommand, or any other LaTeX commands
      in placeholder values. Return plain text content only.
""" + _DO_NOT_MODIFY_SECTION + """
    HARD RULES:
    - Return every key. Core identity fields must have real, non-empty values.
    - Do not invent facts (unless faux=true permits it).
    - Do not truncate mid-sentence. If a bullet is kept, it must be a complete thought.
"""


# ---------------------------------------------------------------------------
# Public call interface — LaTeX
# ---------------------------------------------------------------------------

def CALL_RETRY_TEX(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    last_page_fill_pct: float,
    mbp_analysis=None,
    model: str | None = None,
) -> LLM_O:
    """LaTeX retry — content reduction only."""
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")

    schema = build_response_schema(payload["placeholders"])
    mod_deg = payload.get("mod_deg")
    mod_deg_val = mod_deg.value if hasattr(mod_deg, "value") else str(mod_deg)
    mbp_block = _format_mbp_analysis(mbp_analysis)

    retry_system = SYSTEM_PROMPT + _RETRY_PAGE_SECTION_TEX.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        mbp_block=mbp_block,
    )
    return ask_json(selected, str(payload), schema, system=retry_system)


def CALL_RETRY2_TEX(
    payload: LLM_I,
    actual_pages: int,
    target_pages: int,
    last_page_fill_pct: float,
    mbp_analysis=None,
    model: str | None = None,
) -> LLM_O:
    """LaTeX third call — MBP targeted rephrasing."""
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")

    schema = build_response_schema(payload["placeholders"])
    mod_deg = payload.get("mod_deg")
    mod_deg_val = mod_deg.value if hasattr(mod_deg, "value") else str(mod_deg)
    mbp_block = _format_mbp_analysis(mbp_analysis)
    second_retry_system = SYSTEM_PROMPT + _SECOND_RETRY_SECTION_TEX.format(
        actual_pages=actual_pages,
        target_pages=target_pages,
        mod_deg=mod_deg_val,
        faux=payload.get("faux", False),
        fill_pct_display=round(last_page_fill_pct * 100),
        mbp_block=mbp_block,
    )
    return ask_json(selected, str(payload), schema, system=second_retry_system)


# ---------------------------------------------------------------------------
# Debug / raw
# ---------------------------------------------------------------------------

def CALL_RAW(payload: LLM_I, model: str | None = None) -> str:
    #Call the LLM in plain-text mode.  Returns the raw response string (debug)
    selected = model or DEFAULT_MODEL
    if selected not in MODELS:
        raise ValueError(f"Unknown model: {selected!r}. Available: {list(MODELS)}")
    return ask(selected, str(payload), system=SYSTEM_PROMPT)
