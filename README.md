# 🚧 UNDER CONSTRUCTION 🚧
# STATUS: Mostly Complete

## Issue to solve
Tweaking resumes and cover letters take too long for each new posting.

## Proposed solution
An AI-powered service that dynamically updates resumes with relevant skills and phrasing based on given job descriptions and candidate skills.

## Comparison between similar projects
Many AI resume tools exist (open source and commercial). Typical pattern: extract your info, discard your formatting, and generate the document in their pre-made templates. Resumate is built around a different idea: **keeping your template**. So you rewrite only designated placeholders. And also, for privacy, you can *choose* what **NOT** to send to remote LLM call and inject sensitive fields locally afterwards.

| | **Resumate** | Typical OSS / SaaS resume AI |
|---|---|---|
| **Template** | You bring your own `.docx`, `.tex`, or `.txt` | Tool-owned HTML, Typst, or form UI |
| **What the LLM edits** | Only placeholder values; layout/fonts/structure stay read-only | Whole resume content (often from scratch) |
| **Output formats** | docx, tex --> PDF, txt from one pipeline | Typically PDF-only |
| **Sensitive data** | `sensitive_fields.json` never sent to the LLM | Contact info usually goes through the model/API |
| **Rewrite control** | `MOD_DEG` (5 levels) + `--faux` | Depends tbh |
| **Page limit (docx/tex)** | Post-render check + retries with char budget + widow targeting | Rare; Rescume uses Typst-only auto-fit; HR-Breaker relies on fixed HTML layout |

## How to Run

### Installation

#### Prereqs
Make sure to have:
- Python 3.11+
- Node.js 18+ / npm
- LibreOffice (on PATH) - required page-count checks
- pdflatex - required for .tex -> PDF rendering
- Ollama (optional) - for local LLM inference

- python packages in project-root/requirements.txt
    > pip install -r requirements.txt

- node deps (root+frontend)
    > npm install

    > npm install --prefix frontend/resumate-webapp

- Configure your LLM API keys by editing `backend/llm_integration/AI_API/.env`

### Option 1: GUI
From project root: starts FastAPI + Vue dev server together. Run in terminal:
> npm run dev

API:    http://localhost:8000
UI:     http://localhost:5173

Option to run the above two services separately:
Terminal 1:
> uvicorn backend.api.main:app --reload
Terminal 2:
> npm run dev --prefix frontend/resumate-webapp

### Option 2: CLI ONLY
Default (uses all default flags)
> python -m backend.main

#### Examples:

1. Print usage examples
> python -m backend.main examples

2. Choose model + posting
> python -m backend.main -m claude/sonnet-4.6 -p posting_4.txt

3. High modification degree + faux skills
> python -m backend.main -m deepseek/chat -p posting_2.txt --moddeg high --faux

4. Render as LaTeX/PDF
> python -m backend.main -m claude/sonnet-4.6 -p posting_4.txt -f tex

5. Limit to 1 page (retries automatically if exceeded)
> python -m backend.main -m deepseek/chat -p posting_2.txt --pages 1

6. 1-page limit, auto-confirm second retry without prompting
> python -m backend.main -m claude/sonnet-4.6 -p posting_1.txt -f tex --pages 1 -y

7. Use a local Ollama model
> python -m backend.main -m ollama/qwen2.5:14b -p posting_1.txt

--------------
#### Debugging

1. Output just a raw LLM stream; no file writes
> python -m backend.main -m claude/sonnet-4.6 -p posting_4.txt -o stream

2. Skip LLM: just render template with original placeholders
> python -m backend.main -n -p posting_3.txt -f doc




