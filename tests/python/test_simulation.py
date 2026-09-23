import pytest
from lucroradar_api.simulation import Baseline, Levers, SimulationError, simulate

BASE = Baseline(days=90, sale_gross=1_000_000, sale_discount=50_000, sale_direct_cost=650_000,
                sale_revenue_cost_known=950_000, rental_revenue=300_000, rental_direct_cost=60_000,
                rental_rented_days=6_000, rental_available_days=10_000, receipts=1_100_000,
                open_receivables=800_000, dso_days=55)


def test_zero_levers_reproduce_baseline():
    r = simulate(BASE, Levers())
    assert r["simulated"] == r["baseline"]
    assert r["baseline"]["contribution_margin"] == pytest.approx(300_000 + 240_000)


def test_discount_change_hits_margin_one_to_one_with_constant_volume():
    r = simulate(BASE, Levers(discount_change_pp=-2))
    # -2 p.p. sobre R$ 1 mi bruto = +R$ 20 mil de receita e de margem (custo constante)
    assert r["delta"]["sale_revenue"] == pytest.approx(20_000)
    assert r["delta"]["contribution_margin"] == pytest.approx(20_000)


def test_utilization_scales_revenue_and_costs_and_respects_cap():
    r = simulate(BASE, Levers(utilization_change_pp=10))
    assert r["simulated"]["rental_utilization"] == pytest.approx(0.70)
    assert r["delta"]["rental_revenue"] == pytest.approx(50_000)
    assert r["delta"]["rental_margin"] == pytest.approx(40_000)
    capped = simulate(BASE, Levers(utilization_change_pp=40))
    assert capped["simulated"]["rental_utilization"] == pytest.approx(0.95)
    assert any("limitada" in n for n in capped["notes"])


def test_utilization_never_negative():
    r = simulate(BASE, Levers(utilization_change_pp=-40, max_utilization=0.95))
    assert r["simulated"]["rental_utilization"] == pytest.approx(0.20)
    r2 = simulate(Baseline(**{**BASE.__dict__, "rental_rented_days": 1000}), Levers(utilization_change_pp=-40))
    assert r2["simulated"]["rental_utilization"] == 0


def test_collection_delay_affects_cash_not_margin():
    r = simulate(BASE, Levers(collection_delay_days=15))
    daily = (950_000 + 300_000) / 90
    assert r["delta"]["cash_tied_in_receivables_change"] == pytest.approx(daily * 15)
    assert r["delta"]["contribution_margin"] == 0


def test_limits_are_validated():
    with pytest.raises(SimulationError):
        simulate(BASE, Levers(discount_change_pp=25))
    with pytest.raises(SimulationError):
        simulate(BASE, Levers(max_utilization=1.2))


def test_result_is_labeled_as_not_guaranteed():
    r = simulate(BASE, Levers(discount_change_pp=1))
    assert "não é ganho realizado" in r["disclaimer"].lower()
    assert r["assumptions"] and r["limitations"]
