import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_analyze import router as analyze_router
from src.api.routes_cases import router as cases_router
from src.api.routes_chat import router as chat_router
from src.api.routes_triage import router as triage_router
from src.api.routes_qr import router as qr_router
from src.config import settings
from src.rag.qdrant_schema import ensure_collection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _run_sql_migrations() -> None:
    """Execute .sql migration files against PostgreSQL.

    Each file MUST be idempotent (CREATE IF NOT EXISTS, ON CONFLICT DO NOTHING).
    No migration tracking table — idempotency is enforced per-file by convention.
    Fails open: app starts without pharma data if PostgreSQL is unreachable,
    because the core analyze/triage flow does not require it.
    """
    try:
        with psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        ) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                    cursor.execute(sql_file.read_text())
                    logger.info("Migration applied: %s", sql_file.name)
    except Exception as e:
        logger.error("PostgreSQL migrations skipped: %s", e)


def _ensure_qdrant() -> None:
    """Create Qdrant collection if missing (idempotent).

    Fails open: RAG search degrades gracefully if Qdrant is unreachable.
    """
    try:
        ensure_collection()
    except Exception as e:
        logger.error("Qdrant init skipped: %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    _run_sql_migrations()
    _ensure_qdrant()
    yield


app = FastAPI(
    title="Howl Vision API",
    version="0.1.0",
    description="Veterinary AI Copilot powered by Gemma 4",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(analyze_router)
app.include_router(cases_router)
app.include_router(chat_router)
app.include_router(triage_router)
app.include_router(qr_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend"}
