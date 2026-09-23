"""Rotas REST (somente leitura sobre dados compartilhados)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import alerts, metrics, proposal
from ..config import get_settings
from ..filters import FilterError, Filters, build_filters
from ..simulation import Levers, SimulationError, simulate

router = APIRouter(prefix="/api/v1")


def filters_dep(
    start: Annotated[str | None, Query(pattern=r"^(\d{4}-\d{2})?$")] = None,
    end: Annotated[str | None, Query(pattern=r"^(\d{4}-\d{2})?$")] = None,
    business_line: Annotated[str | None, Query(max_length=10)] = None,
    segment: Annotated[str | None, Query(max_length=40)] = None,
    region: Annotated[str | None, Query(max_length=40)] = None,
    product_line: Annotated[str | None, Query(max_length=60)] = None,
    compare: Annotated[str, Query(pattern="^(previous|yoy)$")] = "previous",
) -> Filters:
    meta = metrics.get_meta()
    try:
        return build_filters(start=start or None, end=end or None, business_line=business_line or None,
                             segment=segment or None, region=region or None,
                             product_line=product_line or None, compare=compare,
                             options=meta["options"], window=(meta["window_start"], meta["window_end"]))
    except FilterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


F = Annotated[Filters, Depends(filters_dep)]


@router.get("/meta")
def meta():
    m = metrics.get_meta()
    s = get_settings()
    return {**m, "window_start": m["window_start"].strftime("%Y-%m"),
            "window_end": m["window_end"].strftime("%Y-%m"),
            "repository_url": s.repository_url,
            "copilot_mode": "llm" if s.llm_enabled else "demo",
            "company": "Nexo Equipamentos (empresa fictícia)"}


@router.get("/executive/summary")
def executive_summary(f: F):
    return metrics.kpi_summary(f)


@router.get("/executive/timeseries")
def executive_timeseries(f: F):
    return metrics.timeseries(f)


@router.get("/executive/margin-bridge")
def executive_margin_bridge(f: F):
    return metrics.margin_bridge(f)


@router.get("/alerts")
def get_alerts(f: F):
    return alerts.build_alerts(f)


@router.get("/customers")
def customers(f: F, sort: str = "revenue", q: Annotated[str | None, Query(max_length=60)] = None,
              limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    return metrics.customers_table(f, sort=sort, search=q, limit=limit, offset=offset)


@router.get("/customers/{customer_id}")
def customer(customer_id: Annotated[str, Field(max_length=12)], f: F):
    d = metrics.customer_detail(customer_id, f)
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    return d


@router.get("/products")
def products(f: F):
    return metrics.products_table(f)


@router.get("/drilldown/sales-lines")
def sales_lines(f: F, customer_id: str | None = None, sku: str | None = None,
                limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    return metrics.order_lines(f, customer_id=customer_id, sku=sku, limit=limit, offset=offset)


@router.get("/drilldown/rental-lines")
def rental_lines(f: F, customer_id: str | None = None, sku: str | None = None,
                 limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return metrics.rental_lines(f, customer_id=customer_id, sku=sku, limit=limit)


@router.get("/source-record/{table}/{batch_id}/{row_number}")
def source_record(table: str, batch_id: Annotated[str, Field(max_length=40)], row_number: int):
    try:
        rec = metrics.source_record(table, batch_id, row_number)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not rec:
        raise HTTPException(404, "Registro de origem não encontrado")
    return rec


@router.get("/finance/receivables")
def receivables(f: F):
    return metrics.receivables_overview(f)


@router.get("/finance/cash")
def cash(f: F):
    return metrics.cash_monthly(f)


@router.get("/operations/utilization")
def utilization(f: F):
    return metrics.fleet_utilization(f)


@router.get("/operations/units")
def units(f: F, limit: Annotated[int, Query(ge=1, le=200)] = 30):
    return metrics.idle_units(f, limit)


@router.get("/operations/maintenance")
def maintenance(f: F):
    return metrics.maintenance(f)


@router.get("/operations/stages")
def stages(f: F):
    return {**metrics.stage_times(f), "credit_review_by_value": metrics.credit_review_by_value(f)}


@router.get("/quality/overview")
def quality_overview():
    return metrics.quality_overview()


@router.get("/quality/quarantine")
def quality_quarantine(table: Annotated[str | None, Query(max_length=40)] = None,
                       reason: Annotated[str | None, Query(max_length=80)] = None,
                       limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return metrics.quarantine(table, reason, limit)


@router.get("/quality/duplicates")
def quality_duplicates(min_score: Annotated[float, Query(ge=0, le=1)] = 0.0):
    return metrics.duplicate_candidates(min_score)


class SimulationRequest(BaseModel):
    discount_change_pp: float = Field(0.0, ge=-20, le=20)
    utilization_change_pp: float = Field(0.0, ge=-40, le=40)
    collection_delay_days: float = Field(0.0, ge=-90, le=90)
    max_utilization: float = Field(0.95, ge=0.5, le=1.0)


@router.get("/simulator/baseline")
def simulator_baseline(f: F):
    base, notes = metrics.simulation_baseline(f)
    return {"filters": f.describe(), "baseline": asdict(base), "utilization": base.utilization,
            "notes": notes}


@router.post("/simulator/run")
def simulator_run(req: SimulationRequest, f: F):
    base, notes = metrics.simulation_baseline(f)
    try:
        res = simulate(base, Levers(**req.model_dump()))
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc
    res["notes"] = notes + res["notes"]
    res["filters"] = f.describe()
    res["baseline_inputs"] = asdict(base)
    return res


@router.post("/proposal")
def build_proposal(req: SimulationRequest, f: F):
    return proposal.build(f, Levers(**req.model_dump()))


@router.get("/automation/summary")
def automation_summary(f: F):
    """Resumo compacto para automações (n8n): KPIs, alertas e links."""
    s = metrics.kpi_summary(f)
    a = alerts.build_alerts(f)
    return {
        "generated_for": f.describe(),
        "synthetic_data": True,
        "kpis": {k: {kk: v[kk] for kk in ("current", "previous", "delta", "delta_pct")}
                 for k, v in s["kpis"].items()},
        "alerts": [{"id": x["id"], "severity": x["severity"], "title": x["title"], "summary": x["summary"]}
                   for x in a["alerts"]],
        "alert_count": len(a["alerts"]),
        "high_severity_count": sum(1 for x in a["alerts"] if x["severity"] == "high"),
    }
