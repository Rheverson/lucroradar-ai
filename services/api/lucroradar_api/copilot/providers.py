"""Provedores do copiloto.

- DemoProvider: "Demonstração sem modelo generativo". Perguntas fixas, respostas
  montadas por regras sobre os MESMOS serviços de métricas. Não simula LLM.
- AnthropicProvider: integração real (somente no servidor) com ferramentas
  controladas, laço manual de tool use, limites e tratamento de falhas.

Nos dois casos, as evidências (números) vêm das ferramentas; o texto do modelo
só pode referenciá-las por ID. Números no resumo que não existam nas evidências
são sinalizados.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import asdict
from typing import Protocol

from ..config import Settings
from ..filters import Filters
from .tools import TOOL_SPECS, ToolContext, ToolInputError, run_tool

log = logging.getLogger("lucroradar.copilot")

CAUSALITY_NOTE = ("As evidências mostram associações e contribuições aritméticas observadas nos dados. "
                  "Elas não comprovam causa; confirme com as áreas responsáveis antes de agir.")
BASE_LIMITATIONS = [
    "Dados sintéticos de uma empresa fictícia.",
    "Margem de contribuição não é lucro líquido: exclui despesas fixas, depreciação, impostos e juros.",
]


class CopilotError(RuntimeError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class CopilotProvider(Protocol):
    mode: str

    def answer(self, question: str, base: Filters, question_id: str | None = None) -> dict: ...


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def build_response(*, mode: str, model: str | None, question: str, ctx: ToolContext, summary: str,
                   evidence_ids: list[str], limitations: list[str], actions: list[dict] | None = None) -> dict:
    ev_by_id = {e.id: e for e in ctx.evidence}
    cited = [asdict(ev_by_id[i]) for i in evidence_ids if i in ev_by_id]
    unknown = [i for i in evidence_ids if i not in ev_by_id]
    warnings = list(ctx.warnings)
    if unknown:
        warnings.append(f"Evidências inexistentes ignoradas: {', '.join(unknown)}")
    if not cited and ctx.evidence:
        cited = [asdict(e) for e in ctx.evidence[:4]]
    links, seen = [], set()
    for e in cited:
        if e["link"]:
            key = json.dumps(e["link"], sort_keys=True)
            if key not in seen:
                seen.add(key)
                links.append(e["link"])
    return {
        "mode": mode,
        "mode_label": "Demonstração sem modelo generativo" if mode == "demo" else "Modelo generativo (servidor)",
        "model": model,
        "question": question,
        "summary": summary,
        "filters": ctx.used_filters[0] if ctx.used_filters else ctx.base.describe(),
        "filters_used": ctx.used_filters,
        "evidence": cited,
        "limitations": [*limitations, *BASE_LIMITATIONS],
        "causality_note": CAUSALITY_NOTE,
        "actions": actions or [{"label": "Abrir análise", **lnk} for lnk in links[:3]],
        "tool_calls": ctx.calls,
        "warnings": warnings,
        "unsupported_numbers": unsupported_numbers(summary, ctx),
    }


NUM_RE = re.compile(r"(?<![\w])(?:R\$\s?)?-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?\s?(?:%|p\.p\.|h)")


def unsupported_numbers(text: str, ctx: ToolContext) -> list[str]:
    """Números citados no texto que não aparecem em nenhuma evidência formatada."""
    corpus = " ".join(e.formatted + " " + e.label for e in ctx.evidence)
    out = []
    for m in NUM_RE.finditer(text or ""):
        token = m.group(0).replace("R$ ", "").replace("R$", "").strip()
        core = re.sub(r"\s?(%|p\.p\.|h)$", "", token).lstrip("-+")
        if core and core not in corpus:
            out.append(m.group(0))
    return out


# --------------------------------------------------------------------- demo
DEMO_QUESTIONS = [
    {"id": "why_margin", "question": "Por que a margem de contribuição caiu se a receita cresceu?"},
    {"id": "who_discount", "question": "Quais vendedores e produtos mais pressionaram a margem com desconto?"},
    {"id": "cash_gap", "question": "Por que o caixa não acompanha a receita?"},
    {"id": "idle_fleet", "question": "Quais equipamentos estão ociosos e quanto isso custa?"},
    {"id": "slow_stage", "question": "Qual etapa dos pedidos ficou mais lenta?"},
    {"id": "data_trust", "question": "Posso confiar nesses números? Quais problemas de dados afetam a análise?"},
]

KEYWORDS = [
    ("who_discount", ["desconto", "vendedor"]),
    ("cash_gap", ["caixa", "receb", "vencid", "inadimpl", "dinheiro"]),
    ("idle_fleet", ["ocios", "frota", "utiliza", "equipamento", "manuten"]),
    ("slow_stage", ["etapa", "lent", "gargalo", "credito", "prazo de pedido"]),
    ("data_trust", ["qualidade", "confiar", "dados", "duplic"]),
    ("why_margin", ["margem", "lucro", "sobrando", "caiu", "queda"]),
]


def route_question(question: str) -> str | None:
    q = _norm(question)
    for d in DEMO_QUESTIONS:
        if _norm(d["question"]) == q:
            return d["id"]
    for qid, words in KEYWORDS:
        if any(w in q for w in words):
            return qid
    return None


class DemoProvider:
    mode = "demo"

    def answer(self, question: str, base: Filters, question_id: str | None = None) -> dict:
        qid = question_id or route_question(question)
        ctx = ToolContext(base=base)
        if qid is None:
            return build_response(
                mode=self.mode, model=None, question=question, ctx=ctx,
                summary=("No modo de demonstração respondo apenas às perguntas sugeridas (ou variações com os "
                         "mesmos temas: margem, desconto, caixa, frota, etapas e qualidade dos dados). "
                         "Com uma chave de API configurada no servidor, perguntas livres usam o modelo generativo."),
                evidence_ids=[], limitations=["Pergunta fora do roteiro da demonstração."])
        fn = getattr(self, f"_q_{qid}")
        summary, ids, lims = fn(ctx)
        return build_response(mode=self.mode, model=None, question=question, ctx=ctx, summary=summary,
                              evidence_ids=ids, limitations=lims)

    # Cada roteiro chama as mesmas ferramentas do modo LLM e redige por regras.
    def _q_why_margin(self, ctx):
        k = run_tool(ctx, "get_kpi_summary", {})
        b = run_tool(ctx, "get_margin_variation", {"group_by": "product_line"})
        if not b.get("available", True):
            return b["reason"], [], []
        ev = {e.id: e for e in ctx.evidence}
        effects = sorted(b["effects"], key=lambda e: ev[e["evidence_id"]].value)
        neg = [e for e in effects if ev[e["evidence_id"]].value < 0]
        rev, mpct = k["items"][0], k["items"][2]
        parts = [f"Receita: {ev[rev['evidence_id']].formatted}. Margem de contribuição: "
                 f"{ev[mpct['evidence_id']].formatted}."]
        if neg:
            parts.append("Na ponte de margem, os efeitos que reduziram a margem foram: " +
                         "; ".join(f"{e['effect'].lower()} ({ev[e['evidence_id']].formatted})" for e in neg) + ".")
        worst = b["top_contributors"][0] if b["top_contributors"] else None
        if worst:
            parts.append(f"A linha com maior perda de margem foi {worst['name']} "
                         f"({ev[worst['evidence_id']].formatted}).")
        ids = [rev["evidence_id"], mpct["evidence_id"], b["total"]["evidence_id"],
               *[e["evidence_id"] for e in neg], *([worst["evidence_id"]] if worst else [])]
        return " ".join(parts), ids, ["A ponte usa apenas linhas com custo conhecido."]

    def _q_who_discount(self, ctx):
        b = run_tool(ctx, "get_margin_variation", {"group_by": "salesperson_id", "rank_by": "discount"})
        if not b.get("available", True):
            return b["reason"], [], []
        r = run_tool(ctx, "get_contribution_ranking", {"dimension": "product", "order": "highest_discount", "limit": 3})
        ev = {e.id: e for e in ctx.evidence}
        sp = b["top_contributors"][:3]
        summary = ("Vendedores com maior efeito negativo de desconto na margem: " +
                   "; ".join(f"{s['name']}: {ev[s['evidence_id']].formatted}" for s in sp) +
                   ". Produtos com maior taxa de desconto: " +
                   "; ".join(ev[x["evidence_id"]].label for x in r["rows"]) + ".")
        return summary, [s["evidence_id"] for s in sp] + [x["evidence_id"] for x in r["rows"]], \
            ["Desconto concentrado em um vendedor pode refletir a carteira de clientes, não só a política comercial."]

    def _q_cash_gap(self, ctx):
        k = run_tool(ctx, "get_kpi_summary", {})
        o = run_tool(ctx, "get_overdue_receivables", {"limit": 4})
        ev = {e.id: e for e in ctx.evidence}
        items = {i["metric"]: i["evidence_id"] for i in k["items"]}
        movers = o["movers"][:3]
        summary = (f"Recebimentos: {ev[items['Recebimentos (caixa)']].formatted}; receita: "
                   f"{ev[items['Receita líquida']].formatted}. Conversão de receita em caixa: "
                   f"{ev[items['Recebimentos ÷ receita']].formatted}. O saldo vencido foi "
                   f"{ev[o['total']['evidence_id']].formatted}. Clientes com maior aumento de vencidos: " +
                   "; ".join(f"{ev[m['evidence_id']].label} ({ev[m['evidence_id']].formatted})" for m in movers) + ".")
        return summary, [items["Recebimentos (caixa)"], items["Receita líquida"], items["Recebimentos ÷ receita"],
                         o["total"]["evidence_id"], *[m["evidence_id"] for m in movers]], \
            ["Saídas de caixa (compras, investimento em frota) aparecem em Visão executiva › Caixa."]

    def _q_idle_fleet(self, ctx):
        u = run_tool(ctx, "get_fleet_utilization", {})
        ev = {e.id: e for e in ctx.evidence}
        rows = u["rows"][:3]
        summary = (f"Utilização média da frota: {ev[u['total']['evidence_id']].formatted}. Menores utilizações: " +
                   "; ".join(f"{ev[r['evidence_id']].label}: {ev[r['evidence_id']].formatted}" for r in rows) + ".")
        return summary, [u["total"]["evidence_id"], *[r["evidence_id"] for r in rows]], \
            ["Capital parado é estimado por depreciação linear de 60 meses (gerencial, não contábil)."]

    def _q_slow_stage(self, ctx):
        s = run_tool(ctx, "get_stage_times", {})
        ev = {e.id: e for e in ctx.evidence}

        def ratio(item):
            cur, prev = item["median_hours"], item["median_hours_previous"]
            return cur / prev if cur and prev else 0

        candidates = s["stages"] + [{**b, "stage": f"Análise de crédito ({b['band']})"}
                                    for b in s.get("credit_review_by_value", [])]
        ranked = sorted(candidates, key=ratio, reverse=True)
        top = ranked[0] if ranked else None
        if not top:
            return "Sem etapas com dados no período.", [], []
        summary = (f"A maior desaceleração relativa foi em {top['stage']}: "
                   f"{ev[top['evidence_id']].formatted}.")
        overall = next((x for x in s["stages"] if x["stage"] == "Análise de crédito"), None)
        ids = [top["evidence_id"]]
        if overall and overall["evidence_id"] != top["evidence_id"]:
            summary += f" Na média de todos os pedidos, a mesma etapa ficou em {ev[overall['evidence_id']].formatted}."
            ids.append(overall["evidence_id"])
        return summary, ids, \
            ["Medianas consideram apenas etapas concluídas; pedidos abertos aparecem em Operações.",
             "A faixa de valor usa o valor líquido do pedido (venda) ou o valor mensal contratado (locação)."]

    def _q_data_trust(self, ctx):
        q = run_tool(ctx, "get_data_quality_issues", {})
        ev = {e.id: e for e in ctx.evidence}
        top = q["issues"][:4]
        summary = (f"Cobertura de custo: {ev[q['coverage']['evidence_id']].formatted}. Principais problemas: " +
                   "; ".join(f"{ev[i['evidence_id']].label}: {ev[i['evidence_id']].formatted.split('.')[0]}"
                             for i in top) +
                   ". Registros inválidos ficam em quarentena e duplicidades de clientes não são unificadas "
                   "automaticamente.")
        return summary, [q["coverage"]["evidence_id"], *[i["evidence_id"] for i in top]], []


# --------------------------------------------------------------------- LLM
SYSTEM_PROMPT = """Você é o copiloto analítico do LucroRadar AI, sobre dados SINTÉTICOS de uma empresa fictícia \
brasileira que vende e aluga equipamentos. Responda em português do Brasil.

Regras:
- Use as ferramentas para obter números. Nunca calcule, estime ou invente valores; não faça contas.
- Cada ferramenta devolve evidências com IDs (E1, E2...). Cite apenas IDs recebidos.
- Diferencie associação observada de causa comprovada. Não afirme causa.
- Margem de contribuição não é lucro líquido. Receita não é caixa.
- Os filtros da tela já estão aplicados; só mude o período se a pergunta pedir.
- Se os dados não responderem à pergunta, diga isso.
- Ao terminar, chame a ferramenta submit_answer com: summary (até 6 frases, sem números que não estejam \
nas evidências), evidence_ids e limitations."""

SUBMIT_TOOL = {
    "name": "submit_answer",
    "description": "Entrega a resposta final ao usuário.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "evidence_ids", "limitations"],
        "additionalProperties": False,
    },
}


class AnthropicProvider:
    mode = "llm"

    def __init__(self, settings: Settings):
        import anthropic

        self.settings = settings
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.copilot_timeout_seconds, max_retries=1)

    def answer(self, question: str, base: Filters, question_id: str | None = None) -> dict:
        s = self.settings
        a = self.anthropic
        ctx = ToolContext(base=base)
        deadline = time.monotonic() + s.copilot_timeout_seconds * 2
        messages: list[dict] = [{"role": "user", "content":
                                 f"Filtros da tela: {base.human()}.\n\nPergunta: {question}"}]
        tools = [*TOOL_SPECS, SUBMIT_TOOL]
        tool_calls = 0
        for _turn in range(s.copilot_max_tool_calls + 2):
            if time.monotonic() > deadline:
                raise CopilotError("Tempo limite do copiloto excedido.", 504)
            try:
                resp = self.client.beta.messages.create(
                    model=s.copilot_model,
                    max_tokens=s.copilot_max_output_tokens,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                    output_config={"effort": s.copilot_effort},
                    betas=["server-side-fallback-2026-07-01"],
                    extra_body={"fallbacks": "default"},
                )
            except a.AuthenticationError as exc:
                raise CopilotError("Chave de API inválida no servidor.", 502) from exc
            except a.RateLimitError as exc:
                raise CopilotError("Limite de uso do provedor atingido. Tente novamente em instantes.", 429) from exc
            except a.APITimeoutError as exc:
                raise CopilotError("O provedor do modelo não respondeu a tempo.", 504) from exc
            except a.BadRequestError as exc:
                log.warning("bad request: %s", exc)
                raise CopilotError("Requisição rejeitada pelo provedor do modelo.", 502) from exc
            except a.APIStatusError as exc:
                raise CopilotError(f"Falha no provedor do modelo ({exc.status_code}).", 502) from exc
            except a.APIConnectionError as exc:
                raise CopilotError("Sem conexão com o provedor do modelo.", 503) from exc

            if resp.stop_reason == "refusal":
                raise CopilotError("O modelo recusou a solicitação.", 422)
            if resp.stop_reason == "max_tokens":
                raise CopilotError("Resposta do modelo excedeu o limite de tokens.", 502)
            messages.append({"role": "assistant", "content": resp.content})
            uses = [b for b in resp.content if b.type == "tool_use"]
            submit = next((b for b in uses if b.name == "submit_answer"), None)
            if submit is not None:
                data = submit.input if isinstance(submit.input, dict) else {}
                return build_response(
                    mode=self.mode, model=getattr(resp, "model", s.copilot_model), question=question, ctx=ctx,
                    summary=str(data.get("summary", ""))[:2000],
                    evidence_ids=[str(x) for x in data.get("evidence_ids", [])][:20],
                    limitations=[str(x)[:300] for x in data.get("limitations", [])][:6])
            if not uses:
                text = " ".join(b.text for b in resp.content if b.type == "text")
                return build_response(mode=self.mode, model=s.copilot_model, question=question, ctx=ctx,
                                      summary=text[:2000], evidence_ids=[e.id for e in ctx.evidence[:6]],
                                      limitations=["O modelo não usou o formato estruturado de resposta."])
            results = []
            for u in uses:
                tool_calls += 1
                if tool_calls > s.copilot_max_tool_calls:
                    results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": True,
                                    "content": "Limite de chamadas atingido. Chame submit_answer agora."})
                    continue
                try:
                    out = run_tool(ctx, u.name, u.input)
                    results.append({"type": "tool_result", "tool_use_id": u.id,
                                    "content": json.dumps(out, ensure_ascii=False, default=str)[:12000]})
                except ToolInputError as exc:
                    results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": True,
                                    "content": f"Parâmetro inválido: {exc}"})
            messages.append({"role": "user", "content": results})
        raise CopilotError("O copiloto não concluiu a resposta dentro do limite de etapas.", 502)
