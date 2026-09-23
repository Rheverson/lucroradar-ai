"""Aplicação FastAPI do LucroRadar AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import DatabaseUnavailable, close_pool, query_one
from .routers import api, copilot

log = logging.getLogger("lucroradar")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_pool()


app = FastAPI(title="LucroRadar AI API", version="0.1.0", lifespan=lifespan,
              description="API de métricas sobre dados sintéticos. Somente leitura.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(DatabaseUnavailable)
async def db_unavailable(_: Request, exc: DatabaseUnavailable):
    log.warning("banco indisponível: %s", exc)
    return JSONResponse(status_code=503, content={
        "detail": "Banco de dados indisponível. Verifique se o PostgreSQL está ativo e o pipeline foi executado."})


@app.exception_handler(LookupError)
async def no_data(_: Request, exc: LookupError):
    return JSONResponse(status_code=503, content={
        "detail": f"Dados ainda não carregados: {exc}. Execute o pipeline (make pipeline)."})


@app.get("/api/health")
def health():
    try:
        row = query_one("select reference_date from staging.stg_dataset")
        return {"status": "ok", "database": "ok", "data_loaded": bool(row),
                "copilot_mode": "llm" if get_settings().llm_enabled else "demo"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "degraded", "database": str(exc)[:200]})


app.include_router(api.router)
app.include_router(copilot.router)
