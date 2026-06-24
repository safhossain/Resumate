"""Project-wide shared constants.

Kept dependency-free (no imports from other ``backend`` modules) so any module
can import it without risking a circular import.
"""

# Sentinel value the LLM may place in a placeholder to signal that the entire
# paragraph / bullet point containing that placeholder should be removed.
REMOVE_SENTINEL = "REMOVE_BULLETPOINT"

# Maps the CLI ``-f/--format`` choice to its master resume template filename.
# Shared by the CLI (backend/main.py) and the debug tool (backend/page_metrics.py)
# so the canonical template names live in exactly one place.
TEMPLATE_MAP = {
    "doc": "BASE_TEMPLATE.docx",
    "tex": "BASE_TEMPLATE_2.tex.j2",
    "txt": "BASE_TEMPLATE.txt.j2",
    "pdf": "BASE_RESUME_TEMPL.pdf",  # not supported yet; placeholder for future support
}
