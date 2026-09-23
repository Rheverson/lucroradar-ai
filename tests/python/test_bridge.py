import pytest
from lucroradar_api.bridge import BridgeRow, aggregate_effects, decompose


def row(key, q, gross, disc, margin, **attrs):
    return BridgeRow((key,), q, gross, disc, margin, attrs or {"product_line": key})


def test_hand_calculated_effects():
    # base: 10 un × R$100, 10% desc, custo R$50/un → margem 400
    r0 = [row("A", 10, 1000, 100, 400)]
    # atual: 12 un × R$110, 20% desc, custo R$55/un → receita 1056, custo 660, margem 396
    r1 = [row("A", 12, 1320, 264, 396)]
    res = decompose(r0, r1)
    e = res["effects"]
    assert e["volume"] == pytest.approx(2 * 40)            # (12-10) × m0 (40)
    assert e["price"] == pytest.approx(12 * 10 * 0.9)       # q1 × Δp × (1-d0)
    assert e["discount"] == pytest.approx(12 * 110 * -0.1)  # q1 × p1 × (d0-d1)
    assert e["cost"] == pytest.approx(-12 * 5)              # -q1 × Δc
    assert sum(e.values()) == pytest.approx(396 - 400)
    assert res["residual"] == pytest.approx(0, abs=1e-9)


def test_new_and_discontinued_keys_go_to_volume():
    res = decompose([row("A", 5, 500, 0, 200), row("OLD", 1, 100, 0, 30)],
                    [row("A", 5, 500, 0, 200), row("NEW", 2, 300, 30, 90)])
    assert res["effects"]["volume"] == pytest.approx(90 - 30)
    assert res["residual"] == pytest.approx(0, abs=1e-9)


def test_effects_always_sum_to_delta():
    import random

    rng = random.Random(1)
    r0, r1 = [], []
    for k in range(30):
        for rows in (r0, r1):
            q = rng.randint(1, 50)
            g = q * rng.uniform(100, 1000)
            d = g * rng.uniform(0, 0.3)
            rows.append(row(f"K{k}", q, g, d, (g - d) * rng.uniform(-0.1, 0.5)))
    res = decompose(r0, r1[:25])
    assert res["residual"] == pytest.approx(0, abs=1e-6)


def test_aggregate_by_dimension():
    res = decompose([row("A", 1, 100, 0, 50, product_line="X"), row("B", 1, 100, 0, 50, product_line="X")],
                    [row("A", 1, 100, 10, 40, product_line="X"), row("B", 2, 200, 0, 100, product_line="X")])
    agg = aggregate_effects(res["per_key"], "product_line", top=0)
    assert agg[0]["name"] == "X"
    assert agg[0]["delta"] == pytest.approx(140 - 100)
