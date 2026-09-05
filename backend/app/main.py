"""FastAPI entrypoint. Run: uvicorn app.main:app --reload --port 8000

M1 exposes a health check and the read-only documents slice, so the ingested
vault can be inspected over HTTP. Tasks, proposals and notifications are wired
in at M4; the daily scrape scheduler is wired in at M2 and runs in-process.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import settings
from app.db import engine, init_db
from app.models import Clause, Concept, Document
from app.routers import documents
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Lex Sentinel", version="0.1.0", lifespan=lifespan)

# The Next.js dev server runs on :3000 and calls this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)


@app.get("/health")
def health() -> dict:
    """Liveness plus a count of what is actually in the knowledge base."""
    with Session(engine) as session:
        counts = {
            "documents": len(session.exec(select(Document)).all()),
            "clauses": len(session.exec(select(Clause)).all()),
            "concepts": len(session.exec(select(Concept)).all()),
        }
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "offline": settings.offline,
        "scheduler_enabled": settings.scheduler_enabled,
        "vault_dir": str(settings.vault_dir),
        "counts": counts,
    }
