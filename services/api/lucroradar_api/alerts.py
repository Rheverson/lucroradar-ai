"""Alertas determinísticos com evidências.

Cada regra usa os serviços de métricas, declara o limiar e aponta para a tela
onde a evidência pode ser verificada. Alertas indicam associação observada;
não afirmam causa.
"""

from __future__ import annotations

from . import metrics
from .filters import Filters

THRESHOLDS = {
    "margin_drop_pp": 1.5,
    "discount_rise_pp": 1.0,
    "overdue_growth_pct": 0.15,
    "low_utilization": 0.50,
    "maintenance_days": 30,
    "stage_slowdown_ratio": 1.5,
    "cost_coverage_min": 0.95,
}


def _fmt_brl(v: float) -> str:
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"{'-' if v < 0 else ''}R$ {s}"


def _pp(v: float) -> str:
    return f"{v * 100:+.1f}".replace(".", ",") + " p.p."


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def _query_string(f: Filters) -> dict:
    q = {"start": f.period.start.strftime("%Y-%m"), "end": f.period.end.strftime("%Y-%m")}
    q.update(f.dims())
    return q


def build_alerts(f: Filters) -> dict:
    alerts: list[dict] = []
    summary = metrics.kpi_summary(f)
    k = summary["kpis"]
    q = _query_string(f)
    has_prev = summary["comparison_available"]
    bridge = metrics.margin_bridge(f) if has_prev else None

    # 1. queda de margem de contribuição (%)
    if bridge and bridge.get("available") and k["margin_pct"]["delta"] is not None and \
            k["margin_pct"]["delta"] <= -THRESHOLDS["margin_drop_pp"] / 100:
        effects = sorted(bridge["effects"], key=lambda e: e["value"])
        evidence = [
            {"label": "Margem de contribuição (%)",
             "value": f"{_pct(k['margin_pct']['previous'])} → {_pct(k['margin_pct']['current'])}"},
            {"label": "Receita líquida",
             "value": f"{_fmt_brl(k['net_revenue']['previous'])} → {_fmt_brl(k['net_revenue']['current'])}"},
        ] + [{"label": f"Efeito {e['label'].lower()} na margem (R$)", "value": _fmt_brl(e["value"])}
             for e in effects if e["value"] < 0][:3]
        alerts.append({
            "id": "margin_drop",
            "severity": "high",
            "title": "Margem de contribuição caiu enquanto a receita variou "
                     f"{_pct(k['net_revenue']['delta_pct'])}",
            "summary": (f"A margem percentual variou {_pp(k['margin_pct']['delta'])}; os efeitos negativos na "
                        f"ponte de margem foram: {', '.join(e['label'].lower() for e in effects if e['value'] < 0)[:120]}."),
            "evidence": evidence,
            "rule": f"Margem % caiu mais de {THRESHOLDS['margin_drop_pp']} p.p. vs. período de comparação.",
            "link": {"path": "/executivo", "query": q, "anchor": "ponte-de-margem"},
        })

    # 2. aumento de desconto (venda)
    if bridge and bridge.get("available") and k["discount_rate"]["delta"] is not None and \
            k["discount_rate"]["delta"] >= THRESHOLDS["discount_rise_pp"] / 100:
        sp = sorted(bridge["by"]["salesperson_id"], key=lambda r: r["discount"])[:3]
        alerts.append({
            "id": "discount_rise",
            "severity": "high",
            "title": "Desconto médio subiu",
            "summary": (f"A taxa de desconto passou de {_pct(k['discount_rate']['previous'])} para "
                        f"{_pct(k['discount_rate']['current'])}. Concentração nos vendedores "
                        f"{', '.join(r['name'] for r in sp)}."),
            "evidence": [{"label": f"Efeito desconto — vendedor {r['name']}", "value": _fmt_brl(r["discount"])}
                         for r in sp],
            "rule": f"Taxa de desconto subiu mais de {THRESHOLDS['discount_rise_pp']} p.p.",
            "link": {"path": "/clientes-produtos", "query": {**q, "sort": "discount"}},
        })

    # 3. custo direto por unidade subindo mais que o preço
    if bridge and bridge.get("available"):
        worst_cost = sorted(bridge["by"]["product_line"], key=lambda r: r["cost"])[:2]
        for r in worst_cost:
            if r["cost"] < -0.01 * max(1.0, abs(bridge["margin_previous"])) and r["cost"] + r["price"] < 0:
                alerts.append({
                    "id": f"cost_pressure_{r['name']}",
                    "severity": "medium",
                    "title": f"Custo direto pressiona a margem em {r['name']}",
                    "summary": (f"O efeito custo em {r['name']} foi {_fmt_brl(r['cost'])}, não compensado "
                                f"por preço ({_fmt_brl(r['price'])})."),
                    "evidence": [{"label": "Efeito custo", "value": _fmt_brl(r["cost"])},
                                 {"label": "Efeito preço de lista", "value": _fmt_brl(r["price"])},
                                 {"label": "Variação total da margem da linha", "value": _fmt_brl(r["delta"])}],
                    "rule": "Efeito custo negativo > 1% da margem base e maior que o efeito preço.",
                    "link": {"path": "/clientes-produtos", "query": {**q, "product_line": r["name"]}},
                })

    # 4. vencidos crescendo
    ov = k["overdue"]
    if has_prev and ov["delta_pct"] is not None and ov["delta_pct"] >= THRESHOLDS["overdue_growth_pct"]:
        movers = metrics.overdue_by_customer_change(f, limit=4)
        alerts.append({
            "id": "overdue_growth",
            "severity": "high",
            "title": "Valores vencidos cresceram",
            "summary": (f"O saldo vencido foi de {_fmt_brl(ov['previous'])} para {_fmt_brl(ov['current'])} "
                        f"({_pct(ov['delta_pct'])}), enquanto os recebimentos variaram "
                        f"{_pct(k['receipts']['delta_pct'])}."),
            "evidence": [{"label": f"{m['legal_name']} ({m['segment']})",
                          "value": f"{_fmt_brl(m['overdue_previous'])} → {_fmt_brl(m['overdue_current'])}"}
                         for m in movers],
            "rule": f"Saldo vencido no fechamento cresceu ≥ {THRESHOLDS['overdue_growth_pct']:.0%}.",
            "link": {"path": "/executivo", "query": q, "anchor": "recebiveis"},
        })

    # 5. frota ociosa
    fleet = metrics.fleet_utilization(f)
    low = [r for r in fleet["by_sku"] if r["time_utilization"] is not None
           and r["time_utilization"] < THRESHOLDS["low_utilization"] and r["available_days"] > 200]
    low.sort(key=lambda r: -(r["idle_depreciation"] or 0))
    if low:
        alerts.append({
            "id": "idle_fleet",
            "severity": "medium",
            "title": "Equipamentos com baixa utilização",
            "summary": (f"{len(low)} produto(s) da frota com utilização abaixo de "
                        f"{THRESHOLDS['low_utilization']:.0%} no período. Capital parado estimado "
                        f"(depreciação dos dias ociosos): {_fmt_brl(sum(r['idle_depreciation'] or 0 for r in low))}."),
            "evidence": [{"label": f"{r['sku']} — {r['description']}",
                          "value": (f"utilização {_pct(r['time_utilization'])} "
                                    f"(antes {_pct(r['time_utilization_previous'])}), {r['units']} unidades "
                                    f"(antes {r['units_previous'] or '—'})")}
                         for r in low[:3]],
            "rule": f"Utilização < {THRESHOLDS['low_utilization']:.0%} com mais de 200 unidade-dia disponíveis.",
            "link": {"path": "/operacoes", "query": q},
        })

    # 6. manutenção longa
    mt = metrics.maintenance(f)
    long_open = [m for m in mt["open"] if m["days_in_maintenance"] >= THRESHOLDS["maintenance_days"]]
    if long_open:
        alerts.append({
            "id": "long_maintenance",
            "severity": "medium",
            "title": f"{len(long_open)} unidade(s) em manutenção há mais de {THRESHOLDS['maintenance_days']} dias",
            "summary": "Unidades paradas reduzem a capacidade disponível para locação.",
            "evidence": [{"label": f"{m['unit_id']} ({m['sku']})",
                          "value": f"{m['days_in_maintenance']} dias — {m['description']}"}
                         for m in long_open[:4]],
            "rule": f"Ordem de manutenção aberta há ≥ {THRESHOLDS['maintenance_days']} dias na referência.",
            "link": {"path": "/operacoes", "query": q, "anchor": "manutencao"},
        })

    # 7. gargalo de etapa (geral e por faixa de valor do pedido)
    st = metrics.stage_times(f)
    byval = metrics.credit_review_by_value(f)
    bands = {(b["period"], b["faixa"]): b for b in byval}
    for s in st["stages"]:
        prev, cur = s.get("median_hours_previous"), s.get("median_hours")
        slow_all = prev and cur and cur / prev >= THRESHOLDS["stage_slowdown_ratio"] and s["n"] >= 20
        slow_band = None
        if s["stage_code"] == "CREDIT_REVIEW":
            for faixa in ("≥ R$ 30 mil", "< R$ 30 mil"):
                c, p = bands.get(("current", faixa)), bands.get(("previous", faixa))
                if c and p and p["median_hours"] and c["n"] >= 20 and \
                        c["median_hours"] / p["median_hours"] >= THRESHOLDS["stage_slowdown_ratio"]:
                    slow_band = (faixa, p, c)
                    break
        if not (slow_all or slow_band):
            continue
        evidence = [{"label": f"Mediana geral em {s['stage_label']}", "value": f"{prev:.0f} h → {cur:.0f} h"}]
        evidence += [{"label": f"Pedidos {b['faixa']} ({'atual' if b['period'] == 'current' else 'comparação'})",
                      "value": f"mediana {b['median_hours']:.0f} h em {b['n']} pedidos"} for b in byval]
        text = (f"A mediana geral passou de {prev:.0f} h para {cur:.0f} h. " if slow_all else "")
        if slow_band:
            faixa, p, c = slow_band
            text += (f"Nos pedidos {faixa}, a mediana passou de {p['median_hours']:.0f} h para "
                        f"{c['median_hours']:.0f} h ({str(round(c['median_hours'] / p['median_hours'], 1)).replace('.', ',')}×).")
        alerts.append({
            "id": f"stage_{s['stage_code'].lower()}",
            "severity": "medium",
            "title": f"Etapa \"{s['stage_label']}\" ficou mais lenta",
            "summary": text + f" {s['open_n']} pedido(s) ainda nesta etapa.",
            "evidence": evidence,
            "rule": (f"Mediana (geral ou por faixa de valor) ≥ {THRESHOLDS['stage_slowdown_ratio']}× a do "
                     "período de comparação, mínimo de 20 pedidos."),
            "link": {"path": "/operacoes", "query": q, "anchor": "etapas"},
        })

    # 8. cobertura de custo
    cov = k["cost_coverage"]["current"]
    if cov is not None and cov < THRESHOLDS["cost_coverage_min"]:
        alerts.append({
            "id": "cost_coverage",
            "severity": "low",
            "title": "Cobertura de custo abaixo do ideal",
            "summary": (f"{_pct(cov)} da receita tem custo conhecido. A margem é calculada só sobre essa "
                        "parcela; custo ausente não é tratado como zero."),
            "evidence": [{"label": "Linhas de venda sem custo", "value": str(summary["breakdown"]["lines_missing_cost"])},
                         {"label": "Cobertura no período de comparação",
                          "value": _pct(k["cost_coverage"]["previous"])}],
            "rule": f"Cobertura < {THRESHOLDS['cost_coverage_min']:.0%}.",
            "link": {"path": "/qualidade", "query": q},
        })

    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: order[a["severity"]])
    return {"filters": f.describe(), "alerts": alerts, "thresholds": THRESHOLDS,
            "note": "Alertas mostram associações observadas nos dados, não causas comprovadas."}
