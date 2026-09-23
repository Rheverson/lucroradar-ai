"""Aplicação FastAPI do LucroRadar AI."""

from __future__ import annotations

import hmac
import logging
import uuid
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


_settings = get_settings()
_settings.validate_for_runtime()
_docs = _settings.expose_api_docs and not _settings.is_production
app = FastAPI(title="LucroRadar AI API", version="0.1.0", lifespan=lifespan,
              description="API de métricas sobre dados sintéticos. Somente leitura.",
              docs_url="/docs" if _docs else None, redoc_url=None,
              openapi_url="/openapi.json" if _docs else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_credentials=False,
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def require_proxy_token(request: Request, call_next):
    """Com PROXY_SHARED_SECRET definido, /api/v1/* só atende o proxy do web.

    A API pública fica restrita ao front-end; o segredo nunca vai ao navegador.
    /api/health continua aberto (sem dados) para verificação do provedor.
    """
    token = _settings.proxy_token
    if token and request.url.path.startswith("/api/v1/"):
        sent = request.headers.get("x-lr-proxy-token", "")
        if not hmac.compare_digest(sent.encode(), token.encode()):
            return JSONResponse(status_code=403, content={"detail": "Acesso permitido apenas pela aplicação web."})
    return await call_next(request)


@app.exception_handler(DatabaseUnavailable)
async def db_unavailable(_: Request, exc: DatabaseUnavailable):
    log.warning("banco indisponível: %s", exc)
    return JSONResponse(status_code=503, content={
        "detail": "Banco de dados indisponível. Verifique se o PostgreSQL está ativo e o pipeline foi executado."})


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    # Detalhes ficam só no log do servidor; o cliente recebe um identificador para suporte.
    error_id = uuid.uuid4().hex[:12]
    log.exception("erro inesperado %s", error_id, exc_info=exc)
    return JSONResponse(status_code=500, content={
        "detail": "Erro interno ao processar a solicitação.", "error_id": error_id})


@app.exception_handler(LookupError)
async def no_data(_: Request, exc: LookupError):
    return JSONResponse(status_code=503, content={
        "detail": "Dados ainda não carregados. Execute o pipeline (make pipeline)."})


@app.get("/api/health")
def health():
    try:
        row = query_one("select reference_date from staging.stg_dataset")
        return {"status": "ok", "database": "ok", "data_loaded": bool(row),
                "copilot_mode": "llm" if get_settings().llm_enabled else "demo"}
    except Exception:  # noqa: BLE001
        log.warning("health: banco indisponível", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})


app.include_router(api.router)
app.include_router(copilot.router)
