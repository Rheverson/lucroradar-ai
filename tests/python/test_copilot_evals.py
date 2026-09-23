"""Avaliações do copiloto com perguntas de resultado conhecido.

Verificam: fidelidade numérica (evidência = serviço de métricas), respeito aos
filtros, ausência de números sem evidência e nota de causalidade.
O modo LLM é testado com um cliente falso (sem rede); a avaliação ao vivo com
chave real está em evals/run_llm_evals.py.
"""

from types import SimpleNamespace

import pytest
from lucroradar_api import metrics
from lucroradar_api.copilot.providers import AnthropicProvider, DemoProvider
from lucroradar_api.filters import build_filters

pytestmark = pytest.mark.db


def F(**kw):
    m = metrics.get_meta()
    return build_filters(start=kw.pop("start", "2026-01"), end=kw.pop("end", "2026-06"),
                         options=m["options"], window=(m["window_start"], m["window_end"]), **kw)


def ask(qid, **filters):
    return DemoProvider().answer("pergunta", F(**filters), qid)


@pytest.mark.parametrize("qid", ["why_margin", "who_discount", "cash_gap", "idle_fleet", "slow_stage", "data_trust"])
def test_every_answer_is_grounded(qid):
    a = ask(qid)
    assert a["mode_label"] == "Demonstração sem modelo generativo"
    assert a["evidence"], "resposta sem evidência"
    assert a["unsupported_numbers"] == []
    assert "não comprovam causa" in a["causality_note"]
    assert a["limitations"] and a["actions"]
    assert a["filters"]["period"]["start"] == "2026-01"


def test_numeric_fidelity_against_metric_service():
    a = ask("why_margin")
    s = metrics.kpi_summary(F())["kpis"]
    by_label = {e["label"]: e for e in a["evidence"]}
    rev = next(v for k, v in by_label.items() if k.startswith("Receita líquida"))
    assert rev["value"] == pytest.approx(s["net_revenue"]["current"])
    mpct = next(v for k, v in by_label.items() if k.startswith("Margem de contribuição (%)"))
    assert mpct["value"] == pytest.approx(s["margin_pct"]["current"])


def test_filters_are_respected():
    a = ask("why_margin", segment="Eventos")
    assert a["filters"]["segment"] == "Eventos"
    s = metrics.kpi_summary(F(segment="Eventos"))["kpis"]
    rev = next(e for e in a["evidence"] if e["label"].startswith("Receita líquida"))
    assert rev["value"] == pytest.approx(s["net_revenue"]["current"])
    assert all(link["query"].get("segment") == "Eventos" for link in a["actions"])


def test_known_answer_late_payers(manifest):
    a = ask("cash_gap")
    labels = " ".join(e["label"] for e in a["evidence"])
    hits = [c for c in manifest["scenarios"]["late_payments"]["customer_ids"] if c in labels]
    assert len(hits) >= 2


def test_known_answer_idle_fleet(manifest):
    a = ask("idle_fleet")
    assert manifest["scenarios"]["idle_fleet"]["sku"] in a["summary"]


def test_known_answer_discount(manifest):
    a = ask("who_discount")
    assert any(sp in a["summary"] for sp in manifest["scenarios"]["discount_escalation"]["salesperson_ids"])


def test_known_answer_bottleneck():
    assert "Análise de crédito" in ask("slow_stage")["summary"]


def test_out_of_scope_question_has_no_invented_answer():
    a = DemoProvider().answer("Qual a previsão do dólar para 2030?", F())
    assert a["evidence"] == [] and "demonstração" in a["summary"]


# ------------------------------------------------ modo LLM com cliente falso
def _block(**kw):
    return SimpleNamespace(**kw)


class FakeMessages:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return self.script[len(self.calls) - 1]


def _fake_provider(script):
    import anthropic
    from lucroradar_api.config import Settings

    p = AnthropicProvider.__new__(AnthropicProvider)
    p.settings = Settings(anthropic_api_key="teste")
    p.anthropic = anthropic
    msgs = FakeMessages(script)
    p.client = SimpleNamespace(beta=SimpleNamespace(messages=msgs))
    return p, msgs


def test_llm_loop_enforces_filters_evidence_and_numbers():
    script = [
        SimpleNamespace(stop_reason="tool_use", model="fake", content=[
            _block(type="tool_use", id="t1", name="get_kpi_summary", input={"segment": "Indústria"})]),
        SimpleNamespace(stop_reason="tool_use", model="fake", content=[
            _block(type="tool_use", id="t2", name="submit_answer", input={
                "summary": "A receita subiu e a margem caiu para R$ 9.999.999.",
                "evidence_ids": ["E1", "E3", "E999"], "limitations": ["teste"]})]),
    ]
    p, msgs = _fake_provider(script)
    a = p.answer("Por que a margem caiu?", F(segment="Eventos"))
    # filtro da tela prevaleceu sobre o pedido do modelo
    assert a["filters"]["segment"] == "Eventos"
    assert any("mantido" in w for w in a["warnings"])
    assert any("E999" in w for w in a["warnings"])
    assert [e["id"] for e in a["evidence"]] == ["E1", "E3"]
    assert "9.999.999" in " ".join(a["unsupported_numbers"])
    # chave e SQL nunca vão para o modelo; ferramentas controladas apenas
    sent = msgs.calls[0]
    assert {t["name"] for t in sent["tools"]} >= {"get_kpi_summary", "submit_answer"}
    assert "select" not in str(sent["tools"]).lower()
    # resultado da ferramenta foi devolvido no segundo turno
    assert msgs.calls[1]["messages"][-2]["content"][0]["tool_use_id"] == "t1"


def test_llm_loop_rejects_unknown_tool_and_bad_params():
    script = [
        SimpleNamespace(stop_reason="tool_use", model="fake", content=[
            _block(type="tool_use", id="a", name="run_sql", input={"sql": "select 1"}),
            _block(type="tool_use", id="b", name="get_kpi_summary", input={"start": "1999-01"})]),
        SimpleNamespace(stop_reason="tool_use", model="fake", content=[
            _block(type="tool_use", id="c", name="submit_answer", input={
                "summary": "Não foi possível obter dados.", "evidence_ids": [], "limitations": []})]),
    ]
    p, msgs = _fake_provider(script)
    a = p.answer("teste", F())
    results = msgs.calls[1]["messages"][-2]["content"]
    assert all(r["is_error"] for r in results)
    assert a["evidence"] == []


def test_llm_refusal_is_reported():
    from lucroradar_api.copilot.providers import CopilotError

    p, _ = _fake_provider([SimpleNamespace(stop_reason="refusal", model="fake", content=[])])
    with pytest.raises(CopilotError):
        p.answer("teste", F())
