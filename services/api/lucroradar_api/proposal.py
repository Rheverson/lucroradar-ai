"""Proposta de ação fundamentada (determinística).

Combina alertas com evidências, ponte de margem e o cenário simulado pelo
usuário. O texto é montado por regras: nenhum número vem de modelo generativo.
"""

from __future__ import annotations

from datetime import date

from . import alerts as alerts_mod
from . import metrics
from .filters import Filters
from .simulation import Levers, simulate

ACTIONS = {
    "margin_drop": ("Acompanhar a ponte de margem mensalmente",
                    "Apresentar volume, preço, desconto e custo separados no comitê comercial."),
    "discount_rise": ("Revisar a alçada de desconto",
                      "Exigir aprovação para descontos acima do padrão histórico e acompanhar por vendedor."),
    "overdue_growth": ("Reforçar a régua de cobrança",
                       "Priorizar os clientes com maior aumento de vencidos e revisar limites de crédito."),
    "idle_fleet": ("Reequilibrar a frota ociosa",
                   "Suspender novas aquisições do item, avaliar transferência entre filiais ou oferta comercial."),
    "long_maintenance": ("Destravar manutenções longas",
                         "Priorizar peças das unidades paradas há mais de 30 dias e revisar fornecedores."),
    "cost_coverage": ("Completar o custo dos itens",
                      "Corrigir a integração de custo para ampliar a cobertura da margem."),
}


def _brl(v: float | None) -> str:
    if v is None:
        return "—"
    return ("-" if v < 0 else "") + "R$ " + f"{abs(v):,.0f}".replace(",", ".")


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def build(f: Filters, levers: Levers) -> dict:
    summary = metrics.kpi_summary(f)
    al = alerts_mod.build_alerts(f)["alerts"]
    base, notes = metrics.simulation_baseline(f)
    sim = simulate(base, levers)
    k = summary["kpis"]
    actions = []
    for a in al:
        key = a["id"] if a["id"] in ACTIONS else (
            "cost_pressure" if a["id"].startswith("cost_pressure") else
            "stage" if a["id"].startswith("stage_") else None)
        if key == "cost_pressure":
            title, detail = ("Rever preço ou custo de aquisição",
                             "Renegociar custo com fornecedores ou reajustar preço de lista da linha afetada.")
        elif key == "stage":
            title, detail = ("Definir prazo para a etapa lenta",
                             "Criar SLA e fila priorizada por valor para a etapa com maior aumento de tempo.")
        elif key:
            title, detail = ACTIONS[key]
        else:
            continue
        actions.append({"title": title, "detail": detail, "based_on": a["title"],
                        "evidence": a["evidence"][:3], "link": a["link"]})
    d = sim["delta"]
    lines = [
        f"# Proposta de ação — {f.human()}",
        "",
        "_Dados sintéticos (empresa fictícia). Documento gerado por regras determinísticas._",
        "",
        "## Diagnóstico",
        f"- Receita líquida: {_brl(k['net_revenue']['current'])} (comparação: {_brl(k['net_revenue']['previous'])}).",
        f"- Margem de contribuição: {_pct(k['margin_pct']['current'])} (comparação: {_pct(k['margin_pct']['previous'])}).",
        f"- Recebimentos: {_brl(k['receipts']['current'])}; vencidos no fechamento: {_brl(k['overdue']['current'])}.",
        "",
        "## Ações propostas",
    ]
    for i, a in enumerate(actions, 1):
        lines.append(f"{i}. **{a['title']}** — {a['detail']} (evidência: {a['based_on']})")
    if not actions:
        lines.append("Nenhum alerta ativo com os filtros atuais.")
    lines += [
        "",
        "## Cenário simulado (não é resultado garantido)",
        f"- Desconto: {levers.discount_change_pp:+.1f} p.p.; utilização: {levers.utilization_change_pp:+.1f} p.p.; "
        f"prazo de recebimento: {levers.collection_delay_days:+.0f} dias.",
        f"- Margem de contribuição: {_brl(sim['baseline']['contribution_margin'])} → "
        f"{_brl(sim['simulated']['contribution_margin'])} ({_brl(d['contribution_margin'])}).",
        f"- Capital em contas a receber: {_brl(d['cash_tied_in_receivables_change'])}.",
        "",
        "## Premissas",
        *[f"- {x}" for x in sim["assumptions"]],
        "",
        "## Limitações",
        *[f"- {x}" for x in sim["limitations"] + notes + sim["notes"]],
        "- Associações observadas nos dados não comprovam causa.",
        "",
        f"_Gerado em {date.today().isoformat()} a partir dos dados com referência {metrics.get_meta()['reference_date']}._",
    ]
    return {"filters": f.describe(), "actions": actions, "simulation": sim, "markdown": "\n".join(lines)}
