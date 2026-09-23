"""Rotas do copiloto. A chave do modelo existe apenas no servidor."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import get_settings
from ..copilot.providers import DEMO_QUESTIONS, AnthropicProvider, CopilotError, DemoProvider
from ..filters import Filters
from .api import filters_dep

router = APIRouter(prefix="/api/v1/copilot")
_hits: dict[str, deque] = defaultdict(deque)
_llm: AnthropicProvider | None = None


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
    if p.mode == "llm" and not req.question_id:
        ip = request.client.host if request.client else "?"
        q = _hits[ip]
        now = time.monotonic()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= s.copilot_requests_per_minute:
            raise HTTPException(429, "Muitas perguntas em sequência. Aguarde um minuto.")
        q.append(now)
    elif p.mode == "llm" and req.question_id:
        # perguntas sugeridas continuam determinísticas mesmo com chave
        p = DemoProvider()
    try:
        return p.answer(question, f, req.question_id)
    except CopilotError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
