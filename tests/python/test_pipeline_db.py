"""Integração: marts reconciliadas com a verdade conhecida do gerador."""

import pytest

pytestmark = pytest.mark.db


def q(db, sql, *params):
    return db.execute(sql, params).fetchall()


def test_sales_revenue_matches_manifest_by_month(db, manifest):
    rows = dict(q(db, """select to_char(month_start,'YYYY-MM'), sum(net_revenue)
                         from marts.mart_contribution_monthly where business_line='sale' group by 1"""))
    for month, expected in manifest["expected"]["sales_net_revenue_by_month"].items():
        assert float(rows[month]) == pytest.approx(expected, abs=0.05), month


def test_rental_revenue_matches_manifest_by_month(db, manifest):
    rows = dict(q(db, """select to_char(month_start,'YYYY-MM'), sum(net_revenue)
                         from marts.mart_contribution_monthly where business_line='rental' group by 1"""))
    for month, expected in manifest["expected"]["rental_revenue_by_month"].items():
        # arredondamento a centavos por item-mês
        assert float(rows[month]) == pytest.approx(expected, abs=5.0), month


def test_overdue_matches_manifest(db, manifest):
    (v,) = q(db, "select sum(open_amount) from marts.fct_receivables where status='overdue'")[0]
    assert float(v) == pytest.approx(manifest["expected"]["overdue_balance_at_reference"], abs=0.05)


def test_all_reconciliations_ok(db):
    bad = q(db, "select check_name from quality.rec_financial_totals where status <> 'ok'")
    assert bad == []
    unbalanced = q(db, "select source_table from quality.rec_row_counts where distinct_keys <> valid_rows + quarantined_rows")
    assert unbalanced == []


def test_quarantine_matches_injected_invalid_records(db, manifest):
    dq = manifest["data_quality"]
    quarantined = {(t, k) for t, k in q(db, "select source_table, record_key from quality.dq_quarantine")}
    for oid in dq["orders_missing_customer"] + dq["orders_invalid_date"]:
        assert ("orders", oid) in quarantined
    for iid in dq["order_items_negative_quantity"] + dq["order_items_unknown_sku"]:
        assert ("order_items", iid) in quarantined
    for rid in dq["receivables_missing_due_date"]:
        assert ("receivables", rid) in quarantined
    for rid in dq["receipts_orphan"]:
        assert ("receipts", rid) in quarantined


def test_missing_cost_is_null_not_zero(db, manifest):
    missing = set(manifest["data_quality"]["order_items_missing_cost"])
    rows = q(db, "select order_item_id, product_cost, contribution_margin from marts.fct_sales_order_lines where not cost_known")
    assert rows and all(pc is None and m is None for _, pc, m in rows)
    assert {r[0] for r in rows} <= missing


def test_duplicate_candidates_found_without_merging(db, manifest):
    pairs = {(a, b): conf for a, b, conf in q(db, """select customer_id_a, customer_id_b, confidence
                                                     from quality.dq_customer_duplicate_candidates""")}
    for p in manifest["data_quality"]["duplicate_customer_pairs"]:
        key = tuple(sorted((p["original"], p["duplicate"])))
        assert pairs.get(key) in ("alta", "media"), p
    for p in manifest["data_quality"]["similar_name_distinct_customers"]:
        key = tuple(sorted((p["a"], p["b"])))
        assert pairs.get(key) in (None, "baixa"), p
    # os dois cadastros continuam existindo separadamente
    ids = {r[0] for r in q(db, "select customer_id from marts.dim_customer")}
    assert all(p["duplicate"] in ids for p in manifest["data_quality"]["duplicate_customer_pairs"])


def test_rerun_does_not_duplicate(db):
    from pathlib import Path

    from lucroradar_ingestion.loader import discover_batches, load_batch

    before = q(db, "select count(*) from raw.order_items")[0][0]
    landing = Path(__file__).resolve().parents[2] / "data" / "landing"
    for b in discover_batches(landing):
        res = load_batch(db, b)
        assert all(f.status == "skipped" for f in res.files)
    assert q(db, "select count(*) from raw.order_items")[0][0] == before


def test_scenarios_are_detectable(db, manifest):
    sc = manifest["scenarios"]
    # desconto: vendedores do cenário muito acima dos demais após o início
    rows = dict(q(db, """select salesperson_id in ('V06','V07'),
                                sum(discount_amount)/sum(gross_amount)
                         from marts.fct_sales_order_lines where is_recognized and revenue_date >= %s
                         group by 1""", sc["discount_escalation"]["from"]))
    assert float(rows[True]) > float(rows[False]) + 0.08
    # clientes com atraso concentram vencidos
    top = [r[0] for r in q(db, """select customer_id from marts.fct_receivables where status='overdue'
                                  group by 1 order by sum(open_amount) desc limit 10""")]
    assert len(set(top) & set(sc["late_payments"]["customer_ids"])) >= 3
    # frota ociosa: utilização cai após a aquisição
    before, after = q(db, """select avg(time_utilization) filter (where month_start < %s),
                                    avg(time_utilization) filter (where month_start >= (%s::date + interval '2 month'))
                             from marts.mart_fleet_utilization_monthly where sku = %s""",
                      sc["idle_fleet"]["acquired_on"], sc["idle_fleet"]["acquired_on"], sc["idle_fleet"]["sku"])[0]
    assert float(after) < float(before) - 0.15
