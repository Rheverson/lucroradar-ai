"""Serviços de métricas: a única fonte de números da API, das alertas e do copiloto.

Todas as consultas leem as marts do dbt com SQL fixo e parâmetros vinculados.
"""

from __future__ import annotations

from datetime import date, timedelta
from time import monotonic

from .bridge import EFFECT_LABELS, BridgeRow, aggregate_effects, decompose
from .db import query, query_one
from .filters import BUSINESS_LINES, Filters, Period, month_label

SEGMENTS_ORDER = ["Construção", "Eventos", "Indústria", "Agronegócio", "Serviços", "Não informado"]


def _pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev)


def _cmp(cur: float | None, prev: float | None, kind: str = "money") -> dict:
    delta = None if cur is None or prev is None else cur - prev
    return {"current": cur, "previous": prev, "delta": delta,
            "delta_pct": _pct_change(cur, prev) if kind == "money" else None, "kind": kind}


# ----------------------------------------------------------------------- meta
_meta_cache: tuple[float, dict] | None = None


def get_meta(force: bool = False) -> dict:
    """Janela de dados, opções de filtro e estado do pipeline (cache de 60 s)."""
    global _meta_cache
    if _meta_cache and not force and monotonic() - _meta_cache[0] < 60:
        return _meta_cache[1]
    ds = query_one("select window_start, reference_date, latest_batch_id, is_synthetic from staging.stg_dataset")
    if not ds:
        raise LookupError("Nenhum lote carregado")
    opts = {
        "segment": [r["segment"] for r in query("select distinct segment from marts.dim_customer order by 1")],
        "region": [r["region"] for r in query("select distinct region from marts.dim_customer order by 1")],
        "product_line": [r["product_line"] for r in query(
            "select distinct product_line from marts.dim_product order by 1")],
        "business_line": list(BUSINESS_LINES),
    }
    opts["segment"].sort(key=lambda s: SEGMENTS_ORDER.index(s) if s in SEGMENTS_ORDER else 99)
    run = query_one("select run_id, status, started_at, finished_at from audit.pipeline_runs "
                    "order by run_id desc limit 1")
    ws: date = ds["window_start"]
    ref: date = ds["reference_date"]
    meta = {
        "window_start": ws.replace(day=1),
        "window_end": ref.replace(day=1),
        "reference_date": ref,
        "latest_batch_id": ds["latest_batch_id"],
        "synthetic": ds["is_synthetic"],
        "options": opts,
        "last_run": run,
    }
    _meta_cache = (monotonic(), meta)
    return meta


def window() -> tuple[date, date]:
    m = get_meta()
    return m["window_start"], m["window_end"]


# ------------------------------------------------------------------ executive
def _contribution_totals(f: Filters, period: Period) -> dict:
    where, params = f.where("contribution", period=period)
    row = query_one(f"""
        select
            coalesce(sum(net_revenue), 0) as net_revenue,
            coalesce(sum(gross_amount), 0) as gross_amount,
            coalesce(sum(discount_amount), 0) as discount_amount,
            coalesce(sum(revenue_cost_known), 0) as revenue_cost_known,
            coalesce(sum(contribution_margin), 0) as contribution_margin,
            coalesce(sum(net_revenue) filter (where business_line = 'sale'), 0) as sale_revenue,
            coalesce(sum(net_revenue) filter (where business_line = 'rental'), 0) as rental_revenue,
            coalesce(sum(gross_amount) filter (where business_line = 'sale'), 0) as sale_gross,
            coalesce(sum(discount_amount) filter (where business_line = 'sale'), 0) as sale_discount,
            coalesce(sum(line_count), 0) as line_count,
            coalesce(sum(lines_missing_cost), 0) as lines_missing_cost
        from marts.mart_contribution_monthly where {where}""", params)
    rev_known = row["revenue_cost_known"]
    row["margin_pct"] = row["contribution_margin"] / rev_known if rev_known else None
    row["cost_coverage"] = rev_known / row["net_revenue"] if row["net_revenue"] else None
    row["discount_rate"] = row["discount_amount"] / row["gross_amount"] if row["gross_amount"] else None
    row["sale_discount_rate"] = row["sale_discount"] / row["sale_gross"] if row["sale_gross"] else None
    return row


def _receipts_total(f: Filters, period: Period) -> float:
    where, params = f.where("receivables", period=period)
    row = query_one(f"select coalesce(sum(amount),0) as v from marts.fct_receipts where {where}", params)
    return row["v"]


def _receivables_snapshot(f: Filters, month: date) -> dict:
    dims, params = f.dims_where("receivables")
    row = query_one(f"""
        select coalesce(sum(open_amount),0) as open_amount,
               coalesce(sum(overdue_amount),0) as overdue_amount,
               coalesce(sum(overdue_over_30),0) as overdue_over_30,
               max(snapshot_date) as snapshot_date
        from marts.mart_receivables_monthly where month_start = %s and {dims}""", [month, *params])
    return row


def _period_available(p: Period) -> bool:
    ws, we = window()
    return p.start >= ws and p.end <= we


def kpi_summary(f: Filters) -> dict:
    cur = _contribution_totals(f, f.period)
    cp = f.comparison_period()
    has_prev = _period_available(cp)
    prev = _contribution_totals(f, cp) if has_prev else None
    rc_cur = _receipts_total(f, f.period)
    rc_prev = _receipts_total(f, cp) if has_prev else None
    snap_cur = _receivables_snapshot(f, f.period.end)
    snap_prev = _receivables_snapshot(f, cp.end) if has_prev else None

    def pv(key):
        return prev[key] if prev else None

    kpis = {
        "net_revenue": _cmp(cur["net_revenue"], pv("net_revenue")),
        "contribution_margin": _cmp(cur["contribution_margin"], pv("contribution_margin")),
        "margin_pct": _cmp(cur["margin_pct"], pv("margin_pct"), "ratio"),
        "receipts": _cmp(rc_cur, rc_prev),
        "overdue": _cmp(snap_cur["overdue_amount"], snap_prev["overdue_amount"] if snap_prev else None),
        "open_receivables": _cmp(snap_cur["open_amount"], snap_prev["open_amount"] if snap_prev else None),
        "discount_rate": _cmp(cur["discount_rate"], pv("discount_rate"), "ratio"),
        "cost_coverage": _cmp(cur["cost_coverage"], pv("cost_coverage"), "ratio"),
        "cash_conversion": _cmp(rc_cur / cur["net_revenue"] if cur["net_revenue"] else None,
                                (rc_prev / prev["net_revenue"]) if prev and prev["net_revenue"] else None,
                                "ratio"),
    }
    return {
        "filters": f.describe(),
        "comparison_available": has_prev,
        "kpis": kpis,
        "breakdown": {"sale_revenue": cur["sale_revenue"], "rental_revenue": cur["rental_revenue"],
                      "lines_missing_cost": cur["lines_missing_cost"], "line_count": cur["line_count"]},
        "overdue_snapshot_date": snap_cur["snapshot_date"],
        "filters_not_applied": {"receivables": f.not_applied("receivables")},
        "definitions": {
            "net_revenue": "Receita reconhecida líquida de descontos (venda no faturamento; locação pró-rata dia).",
            "contribution_margin": "Receita − custos diretos (produto, frete/logística, comissão, manutenção rateada), só em linhas com custo conhecido. Não é lucro líquido.",
            "margin_pct": "Margem de contribuição ÷ receita com custo conhecido.",
            "receipts": "Dinheiro efetivamente recebido de clientes no período (caixa).",
            "overdue": "Saldo em aberto com vencimento anterior à data do fechamento.",
            "cost_coverage": "Parcela da receita com custo direto conhecido.",
        },
    }


def timeseries(f: Filters) -> dict:
    """Série mensal da janela inteira (com os filtros de dimensão), destacando o período."""
    ws, we = window()
    full = f.with_period(Period(ws, we))
    where, params = full.where("contribution")
    contrib = query(f"""
        select month_start,
               sum(net_revenue) as net_revenue,
               sum(net_revenue) filter (where business_line='sale') as sale_revenue,
               sum(net_revenue) filter (where business_line='rental') as rental_revenue,
               sum(contribution_margin) as contribution_margin,
               sum(revenue_cost_known) as revenue_cost_known,
               sum(discount_amount) as discount_amount,
               sum(gross_amount) as gross_amount
        from marts.mart_contribution_monthly where {where}
        group by 1 order by 1""", params)
    rwhere, rparams = full.where("receivables")
    receipts = {r["month_start"]: r["v"] for r in query(
        f"select month_start, sum(amount) v from marts.fct_receipts where {rwhere} group by 1", rparams)}
    dims, dparams = full.dims_where("receivables")
    snaps = {r["month_start"]: r for r in query(f"""
        select month_start, sum(overdue_amount) overdue, sum(open_amount) open_amount
        from marts.mart_receivables_monthly where {dims} group by 1""", dparams)}
    out = []
    for r in contrib:
        m = r["month_start"]
        rk = r["revenue_cost_known"] or 0
        out.append({
            "month": m.strftime("%Y-%m"),
            "label": month_label(m),
            "net_revenue": r["net_revenue"] or 0,
            "sale_revenue": r["sale_revenue"] or 0,
            "rental_revenue": r["rental_revenue"] or 0,
            "contribution_margin": r["contribution_margin"] or 0,
            "margin_pct": (r["contribution_margin"] / rk) if rk else None,
            "discount_rate": (r["discount_amount"] / r["gross_amount"]) if r["gross_amount"] else None,
            "receipts": receipts.get(m, 0),
            "overdue": (snaps.get(m) or {}).get("overdue") or 0,
            "open_receivables": (snaps.get(m) or {}).get("open_amount") or 0,
            "in_period": f.period.start <= m <= f.period.end,
        })
    return {"filters": f.describe(), "series": out}


def _bridge_rows(f: Filters, period: Period) -> list[BridgeRow]:
    where, params = f.where("contribution", period=period)
    rows = query(f"""
        select business_line, sku, product_line, salesperson_id, max(region) as region,
               sum(quantity_cost_known) q, sum(gross_cost_known) g, sum(discount_cost_known) d,
               sum(contribution_margin) m
        from marts.mart_contribution_monthly where {where}
        group by 1, 2, 3, 4""", params)
    return [BridgeRow((r["business_line"], r["sku"], r["salesperson_id"]), r["q"] or 0, r["g"] or 0,
                      r["d"] or 0, r["m"] or 0,
                      {"business_line": BUSINESS_LINES[r["business_line"]], "sku": r["sku"],
                       "product_line": r["product_line"],
                       "salesperson_id": r["salesperson_id"] or "—", "region": r["region"]})
            for r in rows]


def margin_bridge(f: Filters) -> dict:
    cp = f.comparison_period()
    if not _period_available(cp):
        return {"filters": f.describe(), "available": False,
                "reason": "Período de comparação fora da janela de dados."}
    res = decompose(_bridge_rows(f, cp), _bridge_rows(f, f.period))
    effects = [{"key": k, "label": EFFECT_LABELS[k], "value": v} for k, v in res["effects"].items()]
    by_dim = {dim: aggregate_effects(res["per_key"], dim, top=0)
              for dim in ("product_line", "salesperson_id", "business_line", "region")}
    return {
        "filters": f.describe(),
        "available": True,
        "margin_previous": res["margin0"],
        "margin_current": res["margin1"],
        "revenue_previous": res["revenue0"],
        "revenue_current": res["revenue1"],
        "margin_pct_previous": res["margin_pct0"],
        "margin_pct_current": res["margin_pct1"],
        "effects": effects,
        "residual": res["residual"],
        "by": by_dim,
        "method": ("Decomposição por linha de negócio × produto × vendedor, apenas linhas com custo "
                   "conhecido. Os efeitos somam exatamente a variação da margem. Mostram contribuições "
                   "aritméticas, não causa comprovada."),
    }


# ------------------------------------------------------- customers & products
CUSTOMER_SORTS = {"revenue": "net_revenue desc", "margin": "contribution_margin desc",
                  "margin_pct": "margin_pct asc nulls last", "discount": "discount_rate desc nulls last",
                  "overdue": "overdue desc nulls last"}


def customers_table(f: Filters, sort: str = "revenue", search: str | None = None,
                    limit: int = 50, offset: int = 0) -> dict:
    where, params = f.where("contribution", alias="m")
    dims, dparams = f.dims_where("receivables", alias="r")
    order = CUSTOMER_SORTS.get(sort, CUSTOMER_SORTS["revenue"])
    search_sql = ""
    sparams: list = []
    if search:
        search_sql = "and (c.legal_name ilike %s or c.customer_id ilike %s)"
        sparams = [f"%{search[:60]}%", f"%{search[:60]}%"]
    rows = query(f"""
        with m as (
            select customer_id, sum(net_revenue) net_revenue, sum(gross_amount) gross_amount,
                   sum(discount_amount) discount_amount, sum(revenue_cost_known) revenue_cost_known,
                   sum(contribution_margin) contribution_margin,
                   sum(net_revenue) filter (where business_line='sale') sale_revenue,
                   sum(net_revenue) filter (where business_line='rental') rental_revenue
            from marts.mart_contribution_monthly m where {where} and customer_id is not null
            group by 1
        ),
        r as (
            select customer_id, sum(overdue_amount) overdue
            from marts.mart_receivables_monthly r where month_start = %s and {dims} group by 1
        )
        select c.customer_id, c.legal_name, c.segment, c.region, c.city, c.state, c.salesperson_id,
               c.is_duplicate_candidate, c.duplicate_candidate_score,
               m.net_revenue, m.sale_revenue, m.rental_revenue, m.contribution_margin,
               m.revenue_cost_known,
               case when m.revenue_cost_known > 0 then m.contribution_margin / m.revenue_cost_known end margin_pct,
               case when m.gross_amount > 0 then m.discount_amount / m.gross_amount end discount_rate,
               case when m.net_revenue > 0 then m.revenue_cost_known / m.net_revenue end cost_coverage,
               coalesce(r.overdue, 0) overdue,
               count(*) over () as total_rows
        from m join marts.dim_customer c using (customer_id)
        left join r using (customer_id)
        where true {search_sql}
        order by {order}, c.customer_id
        limit %s offset %s""", [*params, f.period.end, *dparams, *sparams, min(limit, 200), offset])
    total = rows[0]["total_rows"] if rows else 0
    for r in rows:
        r.pop("total_rows", None)
    return {"filters": f.describe(), "rows": rows, "total": total,
            "filters_not_applied": {"overdue": f.not_applied("receivables")}}


def products_table(f: Filters, limit: int = 100) -> dict:
    where, params = f.where("contribution")
    rows = query(f"""
        select sku, product_line, business_line,
               sum(quantity) quantity, sum(net_revenue) net_revenue, sum(gross_amount) gross_amount,
               sum(discount_amount) discount_amount, sum(product_cost) product_cost,
               sum(logistics_cost) logistics_cost, sum(commission_cost) commission_cost,
               sum(maintenance_cost) maintenance_cost, sum(revenue_cost_known) revenue_cost_known,
               sum(contribution_margin) contribution_margin, sum(lines_missing_cost) lines_missing_cost
        from marts.mart_contribution_monthly where {where}
        group by 1, 2, 3 order by net_revenue desc limit %s""", [*params, min(limit, 200)])
    desc = {r["sku"]: r["description"] for r in query("select sku, description from marts.dim_product")}
    for r in rows:
        r["description"] = desc.get(r["sku"])
        rk = r["revenue_cost_known"] or 0
        r["margin_pct"] = r["contribution_margin"] / rk if rk else None
        r["discount_rate"] = r["discount_amount"] / r["gross_amount"] if r["gross_amount"] else None
        r["cost_coverage"] = rk / r["net_revenue"] if r["net_revenue"] else None
        r["unit_label"] = "unidade-dia locada" if r["business_line"] == "rental" else "unidades vendidas"
    return {"filters": f.describe(), "rows": rows}


def customer_detail(customer_id: str, f: Filters) -> dict | None:
    c = query_one("select * from marts.dim_customer where customer_id = %s", [customer_id])
    if not c:
        return None
    ws, we = window()
    full = f.with_period(Period(ws, we))
    where, params = full.where("contribution")
    monthly = query(f"""
        select month_start, sum(net_revenue) net_revenue, sum(contribution_margin) contribution_margin,
               sum(revenue_cost_known) revenue_cost_known
        from marts.mart_contribution_monthly where {where} and customer_id = %s
        group by 1 order by 1""", [*params, customer_id])
    for r in monthly:
        r["month"] = r.pop("month_start").strftime("%Y-%m")
        r["margin_pct"] = r["contribution_margin"] / r["revenue_cost_known"] if r["revenue_cost_known"] else None
    dup = query("""
        select * from quality.dq_customer_duplicate_candidates
        where customer_id_a = %s or customer_id_b = %s order by match_score desc""", [customer_id, customer_id])
    recv = query("""
        select receivable_id, document_number, business_line, issue_date, due_date, amount, paid_amount,
               open_amount, status, days_overdue, aging_bucket
        from marts.fct_receivables where customer_id = %s and open_amount > 0
        order by due_date limit 50""", [customer_id])
    return {"customer": c, "monthly": monthly, "duplicate_candidates": dup, "open_receivables": recv}


def order_lines(f: Filters, customer_id: str | None = None, sku: str | None = None,
                limit: int = 50, offset: int = 0) -> dict:
    """Registros de origem (linhas de venda) com referência ao lote e linha do arquivo."""
    if f.business_line == "rental":
        return {"rows": [], "total": 0, "note": "Filtro de locação ativo: linhas de venda ocultas."}
    where, params = f.where("contribution", month_col="revenue_month", skip={"business_line"})
    extra = []
    if customer_id:
        extra.append("customer_id = %s")
        params.append(customer_id)
    if sku:
        extra.append("sku = %s")
        params.append(sku)
    extra_sql = (" and " + " and ".join(extra)) if extra else ""
    rows = query(f"""
        select order_item_id, order_id, customer_id, sku, product_line, revenue_date, quantity,
               unit_list_price, gross_amount, discount_amount, discount_rate, net_revenue, cost_known,
               product_cost, freight_cost, commission_cost, contribution_margin, sku_raw,
               sku_is_legacy_code, source_batch_id, source_row_number, count(*) over () total_rows
        from marts.fct_sales_order_lines
        where is_recognized and {where}{extra_sql}
        order by revenue_date desc, order_item_id limit %s offset %s""",
                 [*params, min(limit, 200), offset])
    total = rows[0]["total_rows"] if rows else 0
    for r in rows:
        r.pop("total_rows", None)
    return {"rows": rows, "total": total}


def rental_lines(f: Filters, customer_id: str | None = None, sku: str | None = None,
                 limit: int = 50) -> dict:
    if f.business_line == "sale":
        return {"rows": [], "total": 0, "note": "Filtro de venda ativo: locações ocultas."}
    where, params = f.where("contribution", skip={"business_line"})
    extra = ""
    if customer_id:
        extra += " and customer_id = %s"
        params.append(customer_id)
    if sku:
        extra += " and sku = %s"
        params.append(sku)
    rows = query(f"""
        select contract_item_id, contract_id, unit_id, sku, product_line, customer_id, month_start,
               active_days, days_in_month, recognized_revenue, list_revenue, discount_amount,
               count(*) over () total_rows
        from marts.fct_rental_revenue_monthly where {where}{extra}
        order by month_start desc, contract_item_id limit %s""", [*params, min(limit, 200)])
    total = rows[0]["total_rows"] if rows else 0
    for r in rows:
        r.pop("total_rows", None)
    return {"rows": rows, "total": total}


SOURCE_TABLES = {"order_items", "orders", "receivables", "receipts", "rental_contract_items",
                 "rental_contracts", "customers", "products", "maintenance_orders", "order_events",
                 "direct_costs", "equipment_units", "payables", "disbursements"}


def source_record(table: str, batch_id: str, row_number: int) -> dict | None:
    if table not in SOURCE_TABLES:
        raise ValueError("Tabela de origem não permitida")
    row = query_one(f"select * from raw.{table} where _batch_id = %s and _row_number = %s",
                    [batch_id, row_number])
    if not row:
        return None
    meta = {k: row.pop(k) for k in list(row) if k.startswith("_")}
    return {"table": table, "fields": row, "lineage": meta}


# ------------------------------------------------------------------- finance
def receivables_overview(f: Filters) -> dict:
    dims, params = f.dims_where("receivables")
    aging = query(f"""
        select aging_bucket, sum(open_amount) open_amount, count(*) titles
        from marts.fct_receivables where open_amount > 0.01 and {dims}
        group by 1""", params)
    order = ["A vencer", "1–30 dias", "31–60 dias", "61–90 dias", "Mais de 90 dias"]
    aging.sort(key=lambda r: order.index(r["aging_bucket"]) if r["aging_bucket"] in order else 9)
    top = query(f"""
        select customer_id, max(customer_name) customer_name, max(segment) segment, max(region) region,
               sum(open_amount) overdue, count(*) titles, max(days_overdue) max_days_overdue
        from marts.fct_receivables where status = 'overdue' and {dims}
        group by 1 order by overdue desc limit 10""", params)
    return {"filters": f.describe(), "aging": aging, "top_overdue_customers": top,
            "as_of": get_meta()["reference_date"],
            "note": "Situação na data de referência dos dados (não varia com o período selecionado).",
            "filters_not_applied": f.not_applied("receivables")}


def overdue_by_customer_change(f: Filters, limit: int = 8) -> list[dict]:
    dims, params = f.dims_where("receivables", alias="r")
    cp = f.comparison_period()
    return query(f"""
        select * from (
            select r.customer_id, c.legal_name, c.segment, c.region,
                   coalesce(sum(r.overdue_amount) filter (where r.month_start = %s), 0) overdue_current,
                   coalesce(sum(r.overdue_amount) filter (where r.month_start = %s), 0) overdue_previous
            from marts.mart_receivables_monthly r join marts.dim_customer c using (customer_id)
            where r.month_start in (%s, %s) and {dims}
            group by 1, 2, 3, 4
        ) x
        order by overdue_current - overdue_previous desc limit %s""",
                 [f.period.end, cp.end, f.period.end, cp.end, *params, limit])


def cash_monthly(f: Filters) -> dict:
    ws, we = window()
    rows = query("""select month_start, direction, category, category_label, amount
                    from marts.mart_cash_monthly where month_start between %s and %s
                    order by month_start""", [ws, we])
    months: dict = {}
    for r in rows:
        m = months.setdefault(r["month_start"], {"month": r["month_start"].strftime("%Y-%m"),
                                                 "label": month_label(r["month_start"]),
                                                 "inflow": 0.0, "outflow": 0.0, "categories": {}})
        m[r["direction"]] += r["amount"]
        m["categories"][r["category_label"]] = m["categories"].get(r["category_label"], 0) + r["amount"]
    series = list(months.values())
    for s in series:
        s["net"] = s["inflow"] - s["outflow"]
        s["in_period"] = f.period.start.strftime("%Y-%m") <= s["month"] <= f.period.end.strftime("%Y-%m")
    forecast = query("select week_start, direction, amount, titles from marts.mart_cash_forecast order by 1")
    return {"series": series, "forecast": forecast,
            "note": "Caixa da empresa inteira: filtros de segmento, região e produto não se aplicam às saídas.",
            "forecast_note": "Previsto = títulos em aberto a vencer nos próximos 90 dias, sem ajuste de atraso."}


# ---------------------------------------------------------------- operations
def fleet_utilization(f: Filters) -> dict:
    where, params = f.where("fleet")
    by_sku = query(f"""
        select sku, product_line, max(units) units, sum(owned_days) owned_days,
               sum(maintenance_days) maintenance_days, sum(available_days) available_days,
               sum(rented_days) rented_days, sum(idle_days) idle_days, sum(idle_depreciation) idle_depreciation
        from marts.mart_fleet_utilization_monthly where {where}
        group by 1, 2 order by 1""", params)
    cp = f.comparison_period()
    prev = {}
    if _period_available(cp):
        pwhere, pparams = f.where("fleet", period=cp)
        prev = {r["sku"]: r for r in query(f"""
            select sku, sum(rented_days)::float / nullif(sum(available_days),0) u, max(units) units
            from marts.mart_fleet_utilization_monthly where {pwhere} group by 1""", pparams)}
    desc = {r["sku"]: r["description"] for r in query("select sku, description from marts.dim_product")}
    for r in by_sku:
        r["description"] = desc.get(r["sku"])
        r["time_utilization"] = r["rented_days"] / r["available_days"] if r["available_days"] else None
        r["fleet_utilization"] = r["rented_days"] / r["owned_days"] if r["owned_days"] else None
        r["maintenance_share"] = r["maintenance_days"] / r["owned_days"] if r["owned_days"] else None
        p = prev.get(r["sku"])
        r["time_utilization_previous"] = p["u"] if p else None
        r["units_previous"] = p["units"] if p else None
    ws, we = window()
    fdims, fparams = f.dims_where("fleet")
    trend = query(f"""
        select month_start, sum(rented_days)::float / nullif(sum(available_days),0) time_utilization,
               sum(maintenance_days)::float / nullif(sum(owned_days),0) maintenance_share,
               sum(idle_depreciation) idle_depreciation, max(units) units_max
        from marts.mart_fleet_utilization_monthly where {fdims} group by 1 order by 1""", fparams)
    for t in trend:
        t["month"] = t.pop("month_start").strftime("%Y-%m")
    tot = {k: sum((r[k] or 0) for r in by_sku) for k in
           ("owned_days", "maintenance_days", "available_days", "rented_days", "idle_days", "idle_depreciation")}
    tot["time_utilization"] = tot["rented_days"] / tot["available_days"] if tot["available_days"] else None
    return {"filters": f.describe(), "by_sku": by_sku, "trend": trend, "totals": tot,
            "definition": ("Utilização = unidade-dia locada ÷ (unidade-dia na frota − unidade-dia em manutenção). "
                           "Manutenção reduz o denominador e é mostrada separadamente."),
            "filters_not_applied": f.not_applied("fleet")}


def idle_units(f: Filters, limit: int = 30) -> dict:
    dims, params = f.dims_where("fleet")
    rows = query(f"""
        select unit_id, sku, product_line, acquisition_date, acquisition_cost, branch,
               owned_days_90d, rented_days_90d, idle_days_90d, maintenance_days_90d,
               last_rented_day, status_at_reference,
               rented_days_90d::float / nullif(owned_days_90d - maintenance_days_90d, 0) utilization_90d
        from marts.mart_unit_utilization where {dims}
        order by utilization_90d asc nulls first, idle_days_90d desc limit %s""", [*params, min(limit, 200)])
    return {"rows": rows, "note": "Últimos 90 dias até a data de referência."}


def maintenance(f: Filters) -> dict:
    dims, params = f.dims_where("fleet")
    open_rows = query(f"""
        select maintenance_id, unit_id, sku, product_line, maintenance_type, opened_at,
               days_in_maintenance, description
        from marts.fct_maintenance_orders where is_open and {dims}
        order by days_in_maintenance desc""", params)
    where, wparams = f.where("fleet", month_col="date_trunc('month', coalesce(closed_at, opened_at))")
    stats = query(f"""
        select maintenance_type, count(*) orders, sum(cost_amount) cost,
               percentile_cont(0.5) within group (order by days_in_maintenance) median_days
        from marts.fct_maintenance_orders where {where} group by 1""", wparams)
    return {"open": open_rows, "stats": stats,
            "note": "Manutenções abertas não têm custo conhecido até o fechamento."}


def stage_times(f: Filters) -> dict:
    colmap = {"business_line": "order_type"}
    where, params = f.where("orders", month_col="entered_month", colmap=colmap)
    cur = query(f"""
        select stage_code, stage_label, stage_order, count(*) n,
               count(*) filter (where is_open) open_n,
               percentile_cont(0.5) within group (order by duration_hours) filter (where not is_open) median_hours,
               percentile_cont(0.9) within group (order by duration_hours) filter (where not is_open) p90_hours
        from marts.fct_order_stage_durations
        where {where} and duration_hours is not null
        group by 1, 2, 3 order by stage_order""", params)
    cp = f.comparison_period()
    prev = {}
    if _period_available(cp):
        pwhere, pparams = f.where("orders", month_col="entered_month", colmap=colmap, period=cp)
        prev = {r["stage_code"]: r for r in query(f"""
            select stage_code,
                   percentile_cont(0.5) within group (order by duration_hours) filter (where not is_open) median_hours
            from marts.fct_order_stage_durations where {pwhere} and duration_hours is not null
            group by 1""", pparams)}
    for r in cur:
        p = prev.get(r["stage_code"])
        r["median_hours_previous"] = p["median_hours"] if p else None
    dims, dparams = f.dims_where("orders", colmap=colmap)
    trend = query(f"""
        select entered_month, stage_code,
               percentile_cont(0.5) within group (order by duration_hours) median_hours, count(*) n
        from marts.fct_order_stage_durations
        where not is_open and duration_hours is not null and {dims}
        group by 1, 2 order by 1""", dparams)
    for t in trend:
        t["month"] = t.pop("entered_month").strftime("%Y-%m")
    stuck = query(f"""
        select o.order_id, o.order_type, o.customer_id, o.segment, o.region, o.current_stage,
               sc.stage_label, o.order_value, o.hours_in_current_stage, o.order_date
        from marts.fct_orders o join reference.stage_catalog sc on sc.stage_code = o.current_stage
        where o.order_status = 'open' and {f.dims_where('orders', alias='o', colmap=colmap)[0]}
        order by o.hours_in_current_stage desc limit 20""", f.dims_where("orders", colmap=colmap)[1])
    status = query_one(f"""
        select count(*) filter (where order_status='completed') completed,
               count(*) filter (where order_status='open') open,
               count(*) filter (where order_status='cancelled') cancelled
        from marts.fct_orders where order_date >= %s and order_date < %s and {dims}""",
                       [f.period.start, f.period.end_exclusive, *dparams])
    return {"filters": f.describe(), "stages": cur, "trend": trend, "open_orders": stuck,
            "status": status,
            "definition": ("Duração = entrada na próxima etapa − entrada na etapa. Medianas usam apenas "
                           "etapas concluídas; etapas ainda abertas aparecem separadamente."),
            "filters_not_applied": f.not_applied("orders")}


def credit_review_by_value(f: Filters) -> list[dict]:
    """Mediana de análise de crédito por faixa de valor do pedido, período atual × comparação."""
    colmap = {"business_line": "order_type"}
    out = []
    for label, period in (("current", f.period), ("previous", f.comparison_period())):
        if not _period_available(period):
            continue
        where, params = f.where("orders", month_col="entered_month", colmap=colmap, period=period)
        for r in query(f"""
            select case when order_value >= 30000 then '≥ R$ 30 mil' else '< R$ 30 mil' end faixa,
                   count(*) n,
                   percentile_cont(0.5) within group (order by duration_hours) median_hours
            from marts.fct_order_stage_durations
            where stage_code = 'CREDIT_REVIEW' and not is_open and {where}
            group by 1""", params):
            out.append({"period": label, **r})
    return out


# ------------------------------------------------------------------- quality
def quality_overview() -> dict:
    issues = query("select * from quality.dq_issue_summary order by handling, affected_records desc")
    rec = query("select * from quality.rec_financial_totals")
    counts = query("select * from quality.rec_row_counts order by source_table")
    runs = query("""
        select r.run_id, r.trigger, r.status, r.started_at, r.finished_at, r.message,
               coalesce(json_agg(json_build_object('step', s.step_name, 'status', s.status,
                   'rows', s.rows_affected, 'detail', s.detail) order by s.step_order)
                   filter (where s.run_id is not null), '[]') steps
        from audit.pipeline_runs r left join audit.pipeline_run_steps s using (run_id)
        group by r.run_id order by r.run_id desc limit 10""")
    batches = query("""select batch_id, as_of_date, status, rows_loaded, rows_rejected, finished_at
                       from audit.load_batches order by batch_seq""")
    cov = query_one("""
        select sum(revenue_cost_known) / nullif(sum(net_revenue), 0) coverage,
               sum(lines_missing_cost) missing
        from marts.mart_contribution_monthly where business_line = 'sale'""")
    return {"issues": issues, "reconciliation": rec, "row_counts": counts, "runs": runs,
            "batches": batches, "sale_cost_coverage": cov}


def quarantine(table: str | None = None, reason: str | None = None, limit: int = 50) -> dict:
    clauses, params = ["true"], []
    if table:
        clauses.append("source_table = %s")
        params.append(table)
    if reason:
        clauses.append("reason = %s")
        params.append(reason)
    rows = query(f"""select source_table, record_key, reason, batch_id, row_number, raw_payload
                     from quality.dq_quarantine where {' and '.join(clauses)}
                     order by source_table, record_key limit %s""", [*params, min(limit, 200)])
    return {"rows": rows}


def duplicate_candidates(min_score: float = 0.0) -> dict:
    rows = query("""select * from quality.dq_customer_duplicate_candidates where match_score >= %s
                    order by match_score desc, combined_sales_revenue desc""", [min_score])
    return {
        "rows": rows,
        "rules": [
            "Mesmo CNPJ (somente dígitos) → confiança alta (0,95).",
            "Nome normalizado ≥ 55% similar, mesma cidade, sem CNPJs conflitantes → 0,40 + 0,45 × similaridade (máx. 0,85).",
            "Nome ≥ 75% similar em cidades diferentes → 0,30 × similaridade (baixa).",
            "CNPJs diferentes e preenchidos nunca geram confiança alta ou média.",
        ],
        "policy": ("Nenhum cadastro é unificado automaticamente. A decisão cabe ao responsável pelo "
                   "cadastro de clientes, conferindo documento e endereço no sistema de origem."),
    }


def days_in_period(p: Period, reference: date) -> int:
    end = min(p.end_exclusive - timedelta(days=1), reference)
    return (end - p.start).days + 1


# ------------------------------------------------------------------ simulator
def simulation_baseline(f: Filters):
    """Base observada para o simulador, com os mesmos filtros da análise."""
    from .simulation import Baseline

    where, params = f.where("contribution")
    row = query_one(f"""
        select
            coalesce(sum(gross_amount) filter (where business_line='sale'), 0) sale_gross,
            coalesce(sum(discount_amount) filter (where business_line='sale'), 0) sale_discount,
            coalesce(sum(revenue_cost_known - contribution_margin) filter (where business_line='sale'), 0) sale_direct_cost,
            coalesce(sum(revenue_cost_known) filter (where business_line='sale'), 0) sale_revenue_cost_known,
            coalesce(sum(net_revenue) filter (where business_line='rental'), 0) rental_revenue,
            coalesce(sum(logistics_cost + maintenance_cost) filter (where business_line='rental'), 0) rental_direct_cost,
            coalesce(sum(quantity) filter (where business_line='rental'), 0) rental_rented_days
        from marts.mart_contribution_monthly where {where}""", params)
    notes = []
    fleet_where, fparams = f.where("fleet")
    fleet = query_one(f"""select coalesce(sum(available_days),0) available_days, coalesce(sum(rented_days),0) rented_days
                          from marts.mart_fleet_utilization_monthly where {fleet_where}""", fparams)
    available = fleet["available_days"]
    if f.segment or f.region:
        notes.append("Com filtro de segmento ou região a frota não pode ser separada por cliente: "
                     "a alavanca de utilização fica desativada.")
        available = 0.0
    if f.business_line == "sale":
        available = 0.0
    ref = get_meta()["reference_date"]
    days = days_in_period(f.period, ref)
    receipts = _receipts_total(f, f.period)
    snap = _receivables_snapshot(f, f.period.end)
    revenue = row["sale_gross"] - row["sale_discount"] + row["rental_revenue"]
    dso = snap["open_amount"] / (revenue / days) if revenue and days else None
    base = Baseline(days=days, sale_gross=row["sale_gross"], sale_discount=row["sale_discount"],
                    sale_direct_cost=row["sale_direct_cost"],
                    sale_revenue_cost_known=row["sale_revenue_cost_known"],
                    rental_revenue=row["rental_revenue"], rental_direct_cost=row["rental_direct_cost"],
                    rental_rented_days=row["rental_rented_days"], rental_available_days=available,
                    receipts=receipts, open_receivables=snap["open_amount"], dso_days=dso)
    return base, notes
