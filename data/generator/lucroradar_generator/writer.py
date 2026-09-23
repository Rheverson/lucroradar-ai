"""Divide o mundo em lotes (carga inicial + incremental) e grava CSVs e manifesto.

Lote 1 ("initial"): situação conhecida no último dia antes do mês de referência.
Lote 2 ("incremental"): novidades do mês de referência + versões atualizadas de
registros que mudaram (contratos encerrados, manutenções concluídas, cadastros
corrigidos). Tabelas de estado são reenviadas com a versão mais recente e a
camada staging escolhe a versão do lote mais novo.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random

from .config import GeneratorConfig
from .issues import inject_issues
from .world import World, build_world, rental_revenue_by_month

TABLE_COLUMNS: dict[str, list[str]] = {
    "customers": ["customer_id", "legal_name", "tax_id", "segment", "region", "city", "state",
                  "salesperson_id", "credit_limit", "created_at"],
    "products": ["sku", "description", "product_line", "unit_of_measure", "sale_list_price",
                 "rental_monthly_rate", "is_rentable", "is_sellable"],
    "equipment_units": ["unit_id", "sku", "serial_number", "acquisition_date", "acquisition_cost",
                        "branch", "retired_at"],
    "orders": ["order_id", "order_type", "customer_id", "salesperson_id", "order_date", "channel"],
    "order_items": ["order_item_id", "order_id", "sku", "product_description", "quantity",
                    "unit_list_price", "discount_amount", "unit_cost"],
    "order_events": ["event_id", "order_id", "stage_code", "event_at"],
    "rental_contracts": ["contract_id", "order_id", "customer_id", "start_date", "planned_end_date",
                         "actual_end_date", "billing_cycle"],
    "rental_contract_items": ["contract_item_id", "contract_id", "unit_id", "sku", "start_date",
                              "end_date", "list_monthly_rate", "agreed_monthly_rate"],
    "maintenance_orders": ["maintenance_id", "unit_id", "maintenance_type", "opened_at", "closed_at",
                           "description", "cost_amount"],
    "direct_costs": ["cost_id", "reference_type", "reference_id", "cost_type", "cost_date", "amount"],
    "receivables": ["receivable_id", "customer_id", "origin_type", "origin_id", "document_number",
                    "issue_date", "due_date", "amount"],
    "receipts": ["receipt_id", "receivable_id", "receipt_date", "amount", "method"],
    "payables": ["payable_id", "supplier_name", "category", "issue_date", "due_date", "amount"],
    "disbursements": ["disbursement_id", "payable_id", "paid_date", "amount"],
}


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _as_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    return v


def split_batches(w: World, cfg: GeneratorConfig, rng: Random) -> dict[str, dict[str, list[dict]]]:
    cut = cfg.incremental_cutoff
    asof1 = cut - timedelta(days=1)
    b1: dict[str, list[dict]] = defaultdict(list)
    b2: dict[str, list[dict]] = defaultdict(list)

    def by_date(table: str, rows: list[dict], key: str) -> None:
        for r in rows:
            (b1 if _as_date(r[key]) < cut else b2)[table].append(r)

    # cadastro de clientes: novos no lote 2 + algumas correções de segmento
    for c in w.customers:
        (b1 if c["created_at"] < cut else b2)["customers"].append(c)
    fixed = [c for c in b1["customers"] if c["segment"] == ""][:4]
    for c in fixed:
        b2["customers"].append({**c, "segment": c.get("_true_segment") or "Construção"})
    b1["products"] = list(w.products)
    by_date("equipment_units", w.units, "acquisition_date")
    by_date("orders", w.orders, "_orig_date")
    order_batch = {o["order_id"]: (1 if _as_date(o["_orig_date"]) < cut else 2) for o in w.orders}
    for it in w.order_items:
        (b1 if order_batch[it["order_id"]] == 1 else b2)["order_items"].append(it)
    by_date("order_events", w.order_events, "event_at")

    # contratos: versão conhecida em asof1 e, se mudou, nova versão no lote 2
    for c in w.rental_contracts:
        if c["start_date"] < cut:
            v1 = {**c, "actual_end_date": c["_true_end"] if c["_true_end"] <= asof1 else None}
            b1["rental_contracts"].append(v1)
            if v1["actual_end_date"] != c["actual_end_date"]:
                b2["rental_contracts"].append(c)
        else:
            b2["rental_contracts"].append(c)
    for it in w.rental_contract_items:
        if it["start_date"] < cut:
            v1 = {**it, "end_date": it["_true_end"] if it["_true_end"] <= asof1 else None}
            b1["rental_contract_items"].append(v1)
            if v1["end_date"] != it["end_date"]:
                b2["rental_contract_items"].append(it)
        else:
            b2["rental_contract_items"].append(it)
    for m in w.maintenance_orders:
        if m["opened_at"] < cut:
            known = m["_true_closed"] <= asof1
            v1 = {**m, "closed_at": m["_true_closed"] if known else None,
                  "cost_amount": m["_true_cost"] if known else None}
            b1["maintenance_orders"].append(v1)
            if v1["closed_at"] != m["closed_at"]:
                b2["maintenance_orders"].append(m)
        else:
            b2["maintenance_orders"].append(m)
    by_date("direct_costs", w.direct_costs, "cost_date")
    by_date("receivables", w.receivables, "issue_date")
    by_date("receipts", w.receipts, "receipt_date")
    by_date("payables", w.payables, "issue_date")
    by_date("disbursements", w.disbursements, "paid_date")
    return {"batch_001_initial": b1, "batch_002_incremental": b2}


def compute_expected(w: World, cfg: GeneratorConfig, dq: dict) -> dict:
    """Totais esperados após as regras de limpeza (calculados pelo gerador)."""
    ref = cfg.reference_date
    start = cfg.window_start
    invalid_orders = set(dq["orders_missing_customer"]) | set(dq["orders_invalid_date"])
    invalid_items = set(dq["order_items_negative_quantity"]) | set(dq["order_items_unknown_sku"])
    invoiced: dict[str, date] = {}
    for ev in w.order_events:
        if ev["stage_code"].strip().upper() == "INVOICED":
            invoiced[ev["order_id"]] = ev["event_at"].date()
    sales_by_month: dict[str, float] = defaultdict(float)
    seen = set()
    for it in w.order_items:
        if it["order_item_id"] in seen:
            continue
        seen.add(it["order_item_id"])
        oid = it["order_id"]
        if oid in invalid_orders or it["order_item_id"] in invalid_items or oid not in invoiced:
            continue
        d = invoiced[oid]
        if d < start or d > ref:
            continue
        net = it["unit_list_price"] * it["quantity"] - it["discount_amount"]
        sales_by_month[d.strftime("%Y-%m")] += net
    rental_by_month: dict[str, float] = defaultdict(float)
    for it in w.rental_contract_items:
        rev = rental_revenue_by_month(max(it["start_date"], start), it["_true_end"],
                                      it["agreed_monthly_rate"], ref + timedelta(days=1))
        for m, v in rev.items():
            rental_by_month[m.strftime("%Y-%m")] += v
    valid_recv = {r["receivable_id"] for r in w.receivables} - set(dq["receivables_missing_due_date"])
    receipts_by_month: dict[str, float] = defaultdict(float)
    seen = set()
    for r in w.receipts:
        if r["receipt_id"] in seen or r["receivable_id"] not in valid_recv:
            continue
        seen.add(r["receipt_id"])
        receipts_by_month[r["receipt_date"].strftime("%Y-%m")] += float(r["amount"])
    paid: dict[str, float] = defaultdict(float)
    seen = set()
    for r in w.receipts:
        if r["receipt_id"] in seen:
            continue
        seen.add(r["receipt_id"])
        paid[r["receivable_id"]] += float(r["amount"])
    overdue = 0.0
    for r in w.receivables:
        if r["receivable_id"] not in valid_recv:
            continue
        amt = r["amount"]
        if isinstance(amt, str):
            amt = float(amt.replace(".", "").replace(",", "."))
        if r["due_date"] < ref:
            overdue += max(0.0, amt - paid.get(r["receivable_id"], 0.0))
    return {
        "sales_net_revenue_by_month": {k: round(v, 2) for k, v in sorted(sales_by_month.items())},
        "rental_revenue_by_month": {k: round(v, 2) for k, v in sorted(rental_by_month.items())},
        "receipts_by_month": {k: round(v, 2) for k, v in sorted(receipts_by_month.items())},
        "overdue_balance_at_reference": round(overdue, 2),
    }


def write_dataset(cfg: GeneratorConfig, out_dir: Path, manifest_dir: Path) -> dict:
    w = build_world(cfg)
    dq = inject_issues(w, cfg.seed, cfg.reference_date)
    batches = split_batches(w, cfg, Random(cfg.seed + 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for batch_name, tables in batches.items():
        bdir = out_dir / batch_name
        bdir.mkdir(parents=True, exist_ok=True)
        files = {}
        for table, cols in TABLE_COLUMNS.items():
            rows = tables.get(table, [])
            path = bdir / f"{table}.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                wr = csv.writer(fh)
                wr.writerow(cols)
                for r in rows:
                    wr.writerow([_fmt(r.get(c)) for c in cols])
            files[table] = {"rows": len(rows),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        asof = (cfg.incremental_cutoff - timedelta(days=1)) if batch_name.endswith("initial") \
            else cfg.reference_date
        meta = {
            "batch_name": batch_name,
            "as_of_date": asof.isoformat(),
            "window_start": cfg.window_start.isoformat(),
            "reference_date": cfg.reference_date.isoformat(),
            "seed": cfg.seed,
            "synthetic": True,
            "files": files,
        }
        (bdir / "_batch.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        summary[batch_name] = {t: f["rows"] for t, f in files.items()}

    manifest = {
        "warning": "Verdade conhecida para testes. A aplicação não deve ler este arquivo.",
        "seed": cfg.seed,
        "reference_date": cfg.reference_date.isoformat(),
        "window_start": cfg.window_start.isoformat(),
        "scenarios": {
            "discount_escalation": {
                "salesperson_ids": ["V06", "V07"],
                "from": w.facts["scenario_dates"]["discount_from"],
                "discount_range": [0.15, 0.26],
                "baseline_discount_mean": 0.05,
            },
            "cost_increase": {
                "product_line": "Geradores",
                "from": w.facts["scenario_dates"]["cost_from"],
                "factor": 1.14,
                "list_price_changed": False,
            },
            "price_adjustment": {"from": w.facts["scenario_dates"]["price_adjustment"],
                                 "factor": 1.04, "excluded_product_line": "Geradores"},
            "late_payments": {
                "segment": "Eventos",
                "customer_ids": w.facts["late_payer_customer_ids"],
                "from_due_date": w.facts["scenario_dates"]["late_from"],
                "delay_days_range": [60, 150],
            },
            "idle_fleet": {
                "sku": "PLT-T12",
                "acquired_on": w.facts["scenario_dates"]["idle_acquisition"],
                "unit_ids": w.facts["idle_expansion_unit_ids"],
                "demand_growth": "nenhum (demanda estável)",
            },
            "maintenance_backlog": {
                "skus": ["PLT-A16", "PLT-A20"],
                "returns_between": [w.facts["scenario_dates"]["maint_from"],
                                    w.facts["scenario_dates"]["maint_to"]],
                "duration_days_range": [55, 110],
            },
            "credit_review_bottleneck": {
                "stage": "CREDIT_REVIEW",
                "from": w.facts["scenario_dates"]["credit_from"],
                "applies_to_orders_at_least": 30000,
                "median_hours_before": 19,
                "median_hours_after": 108,
            },
            "demand_growth_monthly": 0.023,
        },
        "data_quality": dq,
        "expected": compute_expected(w, cfg, dq),
        "batches": summary,
    }
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "ground_truth.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return manifest
