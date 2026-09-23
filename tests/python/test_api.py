import pytest

pytestmark = pytest.mark.db

P = {"start": "2026-01", "end": "2026-06"}


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    m = client.get("/api/v1/meta").json()
    assert m["synthetic"] is True and m["window_end"] == "2026-06"
    assert "anthropic" not in str(m).lower() or m["copilot_mode"] in ("demo", "llm")


def test_segment_filters_partition_the_total(client):
    total = client.get("/api/v1/executive/summary", params=P).json()["kpis"]["net_revenue"]["current"]
    segs = client.get("/api/v1/meta").json()["options"]["segment"]
    parts = sum(client.get("/api/v1/executive/summary", params={**P, "segment": s}).json()
                ["kpis"]["net_revenue"]["current"] for s in segs)
    assert parts == pytest.approx(total, abs=0.05)


def test_business_line_filter_affects_all_blocks(client):
    rental = client.get("/api/v1/executive/summary", params={**P, "business_line": "rental"}).json()
    allb = client.get("/api/v1/executive/summary", params=P).json()
    assert rental["kpis"]["net_revenue"]["current"] < allb["kpis"]["net_revenue"]["current"]
    assert rental["kpis"]["receipts"]["current"] < allb["kpis"]["receipts"]["current"]
    ts = client.get("/api/v1/executive/timeseries", params={**P, "business_line": "rental"}).json()["series"]
    assert all(r["sale_revenue"] == 0 for r in ts)
    lines = client.get("/api/v1/drilldown/sales-lines", params={**P, "business_line": "rental"}).json()
    assert lines["rows"] == []


def test_invalid_filter_returns_422(client):
    assert client.get("/api/v1/executive/summary", params={"start": "2020-01"}).status_code == 422
    assert client.get("/api/v1/executive/summary", params={"segment": "Inexistente"}).status_code == 422


def test_bridge_sums_to_margin_change(client):
    b = client.get("/api/v1/executive/margin-bridge", params=P).json()
    assert sum(e["value"] for e in b["effects"]) == pytest.approx(b["margin_current"] - b["margin_previous"], abs=0.5)


def test_drilldown_reaches_source_record(client):
    lines = client.get("/api/v1/drilldown/sales-lines", params={**P, "limit": 1}).json()["rows"]
    r = lines[0]
    src = client.get(f"/api/v1/source-record/order_items/{r['source_batch_id']}/{r['source_row_number']}").json()
    assert src["fields"]["order_item_id"] == r["order_item_id"]
    assert client.get("/api/v1/source-record/pg_user/x/1").status_code == 400


def test_simulator_matches_baseline_and_is_stateless(client):
    base = client.get("/api/v1/simulator/baseline", params=P).json()["baseline"]
    r1 = client.post("/api/v1/simulator/run", params=P, json={"discount_change_pp": -1}).json()
    coverage = base["sale_revenue_cost_known"] / (base["sale_gross"] - base["sale_discount"])
    # receita sobe 1% do bruto; margem só na parcela com custo conhecido (mesma regra da base)
    assert r1["delta"]["sale_revenue"] == pytest.approx(base["sale_gross"] * 0.01, rel=1e-6)
    assert r1["delta"]["contribution_margin"] == pytest.approx(base["sale_gross"] * 0.01 * coverage, rel=1e-6)
    r0 = client.post("/api/v1/simulator/run", params=P, json={}).json()
    assert r0["delta"]["contribution_margin"] == 0
    assert client.post("/api/v1/simulator/run", params=P, json={"discount_change_pp": 50}).status_code == 422


def test_alerts_have_evidence_and_links(client):
    alerts = client.get("/api/v1/alerts", params=P).json()["alerts"]
    ids = {a["id"] for a in alerts}
    assert {"margin_drop", "discount_rise", "overdue_growth", "idle_fleet"} <= ids
    assert all(a["evidence"] and a["link"]["path"] for a in alerts)


def test_proposal_is_grounded(client):
    p = client.post("/api/proposal".replace("/api", "/api/v1"), params=P, json={"discount_change_pp": -2}).json()
    assert p["actions"] and "não é resultado garantido" in p["markdown"]


def test_quality_endpoints(client):
    q = client.get("/api/v1/quality/overview").json()
    assert q["issues"] and q["runs"] and all(r["status"] == "ok" for r in q["reconciliation"])
    d = client.get("/api/v1/quality/duplicates").json()
    assert d["rows"] and "automaticamente" in d["policy"]


@pytest.mark.parametrize("params", [{}, {"start": "", "end": ""}, {"start": "2026-04", "end": "2026-06"},
                                    {"start": "2025-01", "end": "2025-03"}, {"business_line": "rental"},
                                    {"compare": "yoy", "start": "2026-04", "end": "2026-06"}])
def test_alerts_and_automation_for_several_periods(client, params):
    """Regressão: todas as regras de alerta podem disparar juntas sem erro."""
    r = client.get("/api/v1/automation/summary", params=params)
    assert r.status_code == 200, r.text
    assert r.json()["synthetic_data"] is True
    assert client.get("/api/v1/alerts", params=params).status_code == 200
