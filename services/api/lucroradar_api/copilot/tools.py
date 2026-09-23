"""Ferramentas controladas do copiloto.

- Sem SQL arbitrário: cada ferramenta chama um serviço de métricas fixo.
- Parâmetros validados (mesma validação dos filtros da interface).
- Resultados limitados (top N) e resumidos.
- Cada ferramenta devolve evidências numeradas (E1, E2...) calculadas no servidor;
  a resposta final só pode citar evidências por ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .. import metrics
from ..filters import BUSINESS_LINES, FilterError, Filters, build_filters

MAX_ROWS = 10

FILTER_PROPS = {
    "start": {"type": "string", "description": "Mês inicial AAAA-MM (opcional)"},
    "end": {"type": "string", "description": "Mês final AAAA-MM (opcional)"},
    "business_line": {"type": "string", "enum": ["sale", "rental"],
                      "description": "Venda (sale) ou locação (rental)"},
    "segment": {"type": "string", "description": "Segmento do cliente"},
    "region": {"type": "string", "description": "Região do cliente"},
    "product_line": {"type": "string", "description": "Linha de produto"},
    "compare": {"type": "string", "enum": ["previous", "yoy"],
                "description": "Comparar com período anterior ou mesmo período do ano anterior"},
}


def _schema(extra: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": {**FILTER_PROPS, **(extra or {})},
            "required": required or [], "additionalProperties": False}


TOOL_SPECS: list[dict] = [
    {"name": "get_kpi_summary",
     "description": "Receita, margem de contribuição (%), recebimentos, vencidos, desconto e cobertura de custo "
                    "do período, com comparação.",
     "input_schema": _schema()},
    {"name": "get_margin_variation",
     "description": "Decompõe a variação da margem de contribuição em volume/mix, preço de lista, desconto e custo, "
                    "e mostra os maiores contribuintes por dimensão.",
     "input_schema": _schema({"group_by": {"type": "string",
                                           "enum": ["product_line", "salesperson_id", "business_line", "region"]},
                              "rank_by": {"type": "string", "enum": ["delta", "discount", "cost", "volume", "price"],
                                          "description": "Efeito usado para ordenar os maiores contribuintes negativos"}})},
    {"name": "get_contribution_ranking",
     "description": "Ranking de clientes ou produtos por receita, margem ou desconto (máx. 10 linhas).",
     "input_schema": _schema({"dimension": {"type": "string", "enum": ["customer", "product"]},
                              "order": {"type": "string",
                                        "enum": ["top_revenue", "worst_margin_pct", "highest_discount"]},
                              "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS}},
                             ["dimension"])},
    {"name": "get_overdue_receivables",
     "description": "Saldo vencido por faixa de atraso e clientes que mais aumentaram o vencido.",
     "input_schema": _schema({"limit": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS}})},
    {"name": "get_fleet_utilization",
     "description": "Utilização da frota de locação por produto (dias locados / dias disponíveis), manutenção e "
                    "capital parado estimado.",
     "input_schema": _schema()},
    {"name": "get_stage_times",
     "description": "Tempo mediano por etapa dos pedidos (a partir de eventos) e comparação.",
     "input_schema": _schema()},
    {"name": "get_data_quality_issues",
     "description": "Problemas de qualidade de dados, registros afetados e consequências para as análises.",
     "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
]
TOOL_NAMES = {t["name"] for t in TOOL_SPECS}


def _brl(v: float | None) -> str:
    if v is None:
        return "—"
    return ("-" if v < 0 else "") + "R$ " + f"{abs(v):,.0f}".replace(",", ".")


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def _pp(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:+.1f}".replace(".", ",") + " p.p."


@dataclass
class Evidence:
    id: str
    label: str
    value: Any
    formatted: str
    tool: str
    link: dict | None = None


@dataclass
class ToolContext:
    """Filtros da tela (travados) + registro de evidências da conversa."""

    base: Filters
    evidence: list[Evidence] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_filters: list[dict] = field(default_factory=list)

    def add(self, tool: str, label: str, value: Any, formatted: str, link: dict | None = None) -> str:
        eid = f"E{len(self.evidence) + 1}"
        self.evidence.append(Evidence(eid, label, value, formatted, tool, link))
        return eid


class ToolInputError(ValueError):
    pass


def resolve_filters(ctx: ToolContext, args: dict) -> Filters:
    """Filtros da tela prevalecem; o modelo só pode escolher dimensões vazias e o período."""
    meta = metrics.get_meta()
    base = ctx.base
    dims = {}
    for d in ("business_line", "segment", "region", "product_line"):
        locked = getattr(base, d)
        asked = args.get(d)
        if locked and asked and asked != locked:
            ctx.warnings.append(f"Filtro de {d} da tela mantido ({locked}); pedido do modelo ({asked}) ignorado.")
        dims[d] = locked or asked
    try:
        f = build_filters(
            start=args.get("start") or base.period.start.strftime("%Y-%m"),
            end=args.get("end") or base.period.end.strftime("%Y-%m"),
            compare=args.get("compare") or base.compare,
            options=meta["options"], window=(meta["window_start"], meta["window_end"]), **dims)
    except FilterError as exc:
        raise ToolInputError(str(exc)) from exc
    ctx.used_filters.append(f.describe())
    return f


def _link(f: Filters, path: str, **extra) -> dict:
    q = {"start": f.period.start.strftime("%Y-%m"), "end": f.period.end.strftime("%Y-%m"), **f.dims(), **extra}
    return {"path": path, "query": q}


# ------------------------------------------------------------------ handlers
def t_kpi(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    s = metrics.kpi_summary(f)
    k = s["kpis"]
    link = _link(f, "/executivo")
    out = {"period": f.period.label, "comparison": f.comparison_period().label,
           "filters": f.human(), "comparison_available": s["comparison_available"], "items": []}
    specs = [("net_revenue", "Receita líquida", _brl), ("contribution_margin", "Margem de contribuição (R$)", _brl),
             ("margin_pct", "Margem de contribuição (%)", _pct), ("receipts", "Recebimentos (caixa)", _brl),
             ("overdue", "Saldo vencido no fechamento", _brl), ("discount_rate", "Taxa de desconto", _pct),
             ("cost_coverage", "Cobertura de custo", _pct), ("cash_conversion", "Recebimentos ÷ receita", _pct)]
    for key, label, fmt in specs:
        v = k[key]
        text = f"{fmt(v['current'])} (comparação: {fmt(v['previous'])})"
        eid = ctx.add("get_kpi_summary", f"{label} — {f.period.label}", v["current"], text, link)
        out["items"].append({"evidence_id": eid, "metric": label, "current": text,
                             "change": _pp(v["delta"]) if v["kind"] == "ratio" else _pct(v["delta_pct"])})
    if s["filters_not_applied"]["receivables"]:
        out["note"] = ("Filtros não aplicáveis a recebíveis: " + ", ".join(s["filters_not_applied"]["receivables"]))
    return out


def t_bridge(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    b = metrics.margin_bridge(f)
    if not b["available"]:
        return {"available": False, "reason": b["reason"]}
    link = {**_link(f, "/executivo"), "anchor": "ponte-de-margem"}
    out = {"period": f.period.label, "comparison": f.comparison_period().label, "filters": f.human(),
           "method": b["method"], "effects": [], "top_contributors": []}
    eid = ctx.add("get_margin_variation", "Margem de contribuição: comparação → atual",
                  b["margin_current"] - b["margin_previous"],
                  f"{_brl(b['margin_previous'])} ({_pct(b['margin_pct_previous'])}) → "
                  f"{_brl(b['margin_current'])} ({_pct(b['margin_pct_current'])})", link)
    out["total"] = {"evidence_id": eid}
    for e in b["effects"]:
        eid = ctx.add("get_margin_variation", f"Efeito {e['label'].lower()} na margem", e["value"], _brl(e["value"]), link)
        out["effects"].append({"evidence_id": eid, "effect": e["label"], "value": _brl(e["value"])})
    group = args.get("group_by") or "product_line"
    if group not in b["by"]:
        raise ToolInputError("group_by inválido")
    rank_by = args.get("rank_by") or "delta"
    if rank_by not in ("delta", "discount", "cost", "volume", "price"):
        raise ToolInputError("rank_by inválido")
    rows = sorted(b["by"][group], key=lambda r: r[rank_by])[:5]
    for r in rows:
        eid = ctx.add("get_margin_variation", f"{group}={r['name']}: variação da margem", r["delta"],
                      f"{_brl(r['delta'])} (desconto {_brl(r['discount'])}, custo {_brl(r['cost'])}, "
                      f"volume {_brl(r['volume'])}, preço {_brl(r['price'])})", link)
        out["top_contributors"].append({"evidence_id": eid, "name": r["name"]})
    return out


def t_ranking(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    dim = args.get("dimension")
    if dim not in ("customer", "product"):
        raise ToolInputError("dimension deve ser customer ou product")
    order = args.get("order") or "top_revenue"
    limit = max(1, min(int(args.get("limit") or 5), MAX_ROWS))
    if dim == "customer":
        sort = {"top_revenue": "revenue", "worst_margin_pct": "margin_pct",
                "highest_discount": "discount"}.get(order, "revenue")
        rows = metrics.customers_table(f, sort=sort, limit=limit)["rows"]
        name = lambda r: f"{r['legal_name']} ({r['customer_id']}, {r['segment']})"  # noqa: E731
        path = "/clientes-produtos"
    else:
        rows = metrics.products_table(f)["rows"]
        key = {"top_revenue": lambda r: -(r["net_revenue"] or 0),
               "worst_margin_pct": lambda r: (r["margin_pct"] if r["margin_pct"] is not None else 9),
               "highest_discount": lambda r: -(r["discount_rate"] or 0)}[order]
        rows = sorted(rows, key=key)[:limit]
        name = lambda r: f"{r['sku']} — {r['description']} ({BUSINESS_LINES[r['business_line']]})"  # noqa: E731
        path = "/clientes-produtos"
    out = {"period": f.period.label, "filters": f.human(), "order": order, "rows": []}
    for r in rows:
        eid = ctx.add("get_contribution_ranking", name(r), r["net_revenue"],
                      f"receita {_brl(r['net_revenue'])}, margem {_pct(r['margin_pct'])}, "
                      f"desconto {_pct(r['discount_rate'])}, cobertura de custo {_pct(r['cost_coverage'])}",
                      _link(f, path))
        out["rows"].append({"evidence_id": eid, "name": name(r)})
    return out


def t_overdue(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    limit = max(1, min(int(args.get("limit") or 5), MAX_ROWS))
    s = metrics.kpi_summary(f)["kpis"]
    link = {**_link(f, "/executivo"), "anchor": "recebiveis"}
    out = {"period_end": f.period.end.strftime("%Y-%m"), "filters": f.human(), "movers": []}
    eid = ctx.add("get_overdue_receivables", f"Saldo vencido no fechamento de {f.period.label}",
                  s["overdue"]["current"],
                  f"{_brl(s['overdue']['current'])} (comparação: {_brl(s['overdue']['previous'])}, "
                  f"{_pct(s['overdue']['delta_pct'])})", link)
    out["total"] = {"evidence_id": eid}
    for m in metrics.overdue_by_customer_change(f, limit):
        eid = ctx.add("get_overdue_receivables", f"{m['legal_name']} ({m['customer_id']}, {m['segment']})",
                      m["overdue_current"], f"{_brl(m['overdue_previous'])} → {_brl(m['overdue_current'])}", link)
        out["movers"].append({"evidence_id": eid, "customer": m["legal_name"]})
    nap = f.not_applied("receivables")
    if nap:
        out["note"] = "Filtros não aplicáveis a recebíveis: " + ", ".join(nap)
    return out


def t_fleet(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    u = metrics.fleet_utilization(f)
    link = _link(f, "/operacoes")
    out = {"period": f.period.label, "definition": u["definition"], "rows": []}
    t = u["totals"]
    eid = ctx.add("get_fleet_utilization", f"Utilização da frota — {f.period.label}", t["time_utilization"],
                  f"{_pct(t['time_utilization'])}; capital parado estimado {_brl(t['idle_depreciation'])}", link)
    out["total"] = {"evidence_id": eid}
    for r in sorted(u["by_sku"], key=lambda r: r["time_utilization"] if r["time_utilization"] is not None else 9)[:5]:
        eid = ctx.add("get_fleet_utilization", f"{r['sku']} — {r['description']}", r["time_utilization"],
                      f"utilização {_pct(r['time_utilization'])} (comparação {_pct(r['time_utilization_previous'])}); "
                      f"{r['units']} unidades (antes {r['units_previous'] or '—'}); manutenção {_pct(r['maintenance_share'])}",
                      link)
        out["rows"].append({"evidence_id": eid, "sku": r["sku"]})
    if u["filters_not_applied"]:
        out["note"] = "Filtros não aplicáveis à frota: " + ", ".join(u["filters_not_applied"])
    return out


def t_stages(ctx: ToolContext, args: dict) -> dict:
    f = resolve_filters(ctx, args)
    st = metrics.stage_times(f)
    link = {**_link(f, "/operacoes"), "anchor": "etapas"}
    out = {"period": f.period.label, "definition": st["definition"], "stages": []}
    for s in st["stages"]:
        prev = s["median_hours_previous"]
        prev_txt = "—" if prev is None else f"{prev:.0f} h"
        eid = ctx.add("get_stage_times", f"Mediana em {s['stage_label']}", s["median_hours"],
                      f"{(s['median_hours'] or 0):.0f} h (comparação {prev_txt}); "
                      f"{s['n']} pedidos, {s['open_n']} ainda na etapa", link)
        out["stages"].append({"evidence_id": eid, "stage": s["stage_label"],
                              "median_hours": s["median_hours"], "median_hours_previous": prev})
    bands: dict = {}
    for b in metrics.credit_review_by_value(f):
        bands.setdefault(b["faixa"], {})[b["period"]] = b
    out["credit_review_by_value"] = []
    for faixa, v in sorted(bands.items()):
        cur, prev = v.get("current"), v.get("previous")
        if not cur:
            continue
        prev_txt = f"{prev['median_hours']:.0f} h" if prev else "—"
        eid = ctx.add("get_stage_times", f"Análise de crédito — pedidos {faixa}", cur["median_hours"],
                      f"mediana {cur['median_hours']:.0f} h em {cur['n']} pedidos (comparação {prev_txt})", link)
        out["credit_review_by_value"].append({
            "evidence_id": eid, "band": faixa, "median_hours": cur["median_hours"],
            "median_hours_previous": prev["median_hours"] if prev else None})
    return out


def t_quality(ctx: ToolContext, args: dict) -> dict:
    q = metrics.quality_overview()
    link = {"path": "/qualidade", "query": {}}
    out = {"issues": []}
    cov = q["sale_cost_coverage"]
    eid = ctx.add("get_data_quality_issues", "Cobertura de custo na venda (janela inteira)", cov["coverage"],
                  f"{_pct(cov['coverage'])}; {int(cov['missing'] or 0)} linhas sem custo", link)
    out["coverage"] = {"evidence_id": eid}
    for i in sorted(q["issues"], key=lambda i: -(i["affected_records"] or 0))[:8]:
        eid = ctx.add("get_data_quality_issues", f"{i['issue_label']} ({i['source_table']})", i["affected_records"],
                      f"{i['affected_records']} registros; tratamento: {i['handling']}. {i['consequence']}", link)
        out["issues"].append({"evidence_id": eid, "issue": i["issue_label"]})
    return out


HANDLERS = {
    "get_kpi_summary": t_kpi,
    "get_margin_variation": t_bridge,
    "get_contribution_ranking": t_ranking,
    "get_overdue_receivables": t_overdue,
    "get_fleet_utilization": t_fleet,
    "get_stage_times": t_stages,
    "get_data_quality_issues": t_quality,
}


def run_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    if name not in HANDLERS:
        raise ToolInputError(f"Ferramenta desconhecida: {name}")
    if not isinstance(args, dict):
        raise ToolInputError("Parâmetros devem ser um objeto")
    allowed = set(next(t for t in TOOL_SPECS if t["name"] == name)["input_schema"]["properties"])
    unknown = set(args) - allowed
    if unknown:
        raise ToolInputError(f"Parâmetros não permitidos: {', '.join(sorted(unknown))}")
    ctx.calls.append({"name": name, "input": args})
    return HANDLERS[name](ctx, args)


def with_base(ctx: ToolContext, base: Filters) -> ToolContext:
    return replace(ctx, base=base)
