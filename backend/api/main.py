"""FastAPI application — launch with:  uvicorn backend.api.main:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import upload, placeholders, tailor, sessions, output
from . import session_store

app = FastAPI(title="Resumate API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(placeholders.router, prefix="/api", tags=["placeholders"])
app.include_router(tailor.router, prefix="/api", tags=["tailor"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(output.router, prefix="/api", tags=["output"])

# Serve session artefacts (PDF previews, etc.) as static files
_sessions_dir = session_store.SESSIONS_DIR
_sessions_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/static/sessions",
    StaticFiles(directory=str(_sessions_dir)),
    name="session_static",
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
