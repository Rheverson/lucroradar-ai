"""Rotas do copiloto. A chave do modelo existe apenas no servidor."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import get_settings
from ..copilot.providers import DEMO_QUESTIONS, AnthropicProvider, CopilotError, DemoProvider
from ..filters import Filters
from .api import filters_dep

router = APIRouter(prefix="/api/v1/copilot")
_hits: dict[str, deque] = defaultdict(deque)
_daily = {"day": date.today(), "count": 0}
_lock = threading.Lock()
_llm: AnthropicProvider | None = None


def client_ip(request: Request) -> str:
    """IP do visitante para limites de uso.

    - Com PROXY_SHARED_SECRET: o middleware já exigiu o token; o IP vem de X-LR-Client-IP,
      preenchido pelo proxy do web a partir do cabeçalho da borda do provedor.
    - Com TRUST_FORWARDED_FOR (rede privada, ex.: Compose): primeiro valor de X-Forwarded-For.
    - Caso contrário: IP da conexão. Cabeçalhos enviados pelo cliente são ignorados.
    """
    s = get_settings()
    if s.proxy_token:
        ip = request.headers.get("x-lr-client-ip", "").strip()
        if ip:
            return ip[:64]
    elif s.trust_forwarded_for:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "?"


def enforce_llm_limits(ip: str) -> None:
    """Limite por IP (janela de 60 s) e teto global diário. Estado em memória do processo."""
    s = get_settings()
    now = time.monotonic()
    with _lock:
        if _daily["day"] != date.today():
            _daily.update(day=date.today(), count=0)
        if _daily["count"] >= s.copilot_daily_limit:
            raise HTTPException(429, "Limite diário de perguntas ao modelo atingido. "
                                     "As perguntas demonstrativas continuam disponíveis.")
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= s.copilot_requests_per_minute:
            raise HTTPException(429, "Muitas perguntas em sequência. Aguarde um minuto.")
        if len(_hits) > 10_000:  # evita crescimento sem limite
            _hits.clear()
        q.append(now)
        _daily["count"] += 1


def provider(mode: str | None = None):
    global _llm
    s = get_settings()
    if mode == "demo" or not s.llm_enabled:
        return DemoProvider()
    if _llm is None:
        _llm = AnthropicProvider(s)
    return _llm


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=600)
    question_id: str | None = Field(default=None, max_length=40)
    mode: str | None = Field(default=None, pattern="^(demo|llm)$")


@router.get("/status")
def status():
    s = get_settings()
    return {
        "mode": "llm" if s.llm_enabled else "demo",
        "mode_label": "Modelo generativo (servidor)" if s.llm_enabled else "Demonstração sem modelo generativo",
        "model": s.copilot_model if s.llm_enabled else None,
        "max_question_chars": s.copilot_max_question_chars,
        "limits": {"per_ip_per_minute": s.copilot_requests_per_minute, "daily": s.copilot_daily_limit}
        if s.llm_enabled else None,
        "tools": ["get_kpi_summary", "get_margin_variation", "get_contribution_ranking",
                  "get_overdue_receivables", "get_fleet_utilization", "get_stage_times",
                  "get_data_quality_issues"],
    }


@router.get("/demo-questions")
def demo_questions():
    return {"questions": DEMO_QUESTIONS}


@router.post("/ask")
def ask(req: AskRequest, request: Request, f: Filters = Depends(filters_dep)):  # noqa: B008
    s = get_settings()
    question = req.question.strip()[: s.copilot_max_question_chars]
    p = provider(req.mode)
    if p.mode == "llm" and req.question_id:
        # perguntas sugeridas continuam determinísticas (e sem custo) mesmo com chave
        p = DemoProvider()
    elif p.mode == "llm":
        enforce_llm_limits(client_ip(request))
    try:
        return p.answer(question, f, req.question_id)
    except CopilotError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
