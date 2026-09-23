"""Decomposição determinística da variação da margem de contribuição (ponte de margem).

Para cada chave (linha de negócio × produto × vendedor), com medidas restritas às
linhas de custo conhecido:
    q  = quantidade (venda: unidades; locação: unidade-dia)
    p  = preço de lista médio por unidade        = bruto / q
    d  = taxa de desconto                        = desconto / bruto
    c  = custo direto médio por unidade          = (receita − margem) / q
    m  = margem por unidade                      = p·(1−d) − c

    M1 − M0 = Σ (q1 − q0)·m0                      efeito volume/mix
            + Σ q1·(p1 − p0)·(1 − d0)             efeito preço de lista
            + Σ q1·p1·(d0 − d1)                   efeito desconto
            − Σ q1·(c1 − c0)                      efeito custo

Chaves que só existem em um dos períodos entram inteiramente no efeito
volume/mix. A soma dos efeitos é exatamente igual à variação da margem.
Isto descreve contribuições contábeis, não causalidade.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeRow:
    key: tuple
    quantity: float
    gross: float
    discount: float
    margin: float
    attrs: dict | None = None  # dimensões para agregação (linha de produto, vendedor...)

    @property
    def revenue(self) -> float:
        return self.gross - self.discount

    @property
    def direct_cost(self) -> float:
        return self.revenue - self.margin


EFFECTS = ("volume", "price", "discount", "cost")
EFFECT_LABELS = {
    "volume": "Volume e mix",
    "price": "Preço de lista",
    "discount": "Desconto",
    "cost": "Custo direto",
}


def _unit(r: BridgeRow) -> tuple[float, float, float, float]:
    q = r.quantity
    p = r.gross / q if q else 0.0
    d = r.discount / r.gross if r.gross else 0.0
    c = r.direct_cost / q if q else 0.0
    return p, d, c, p * (1 - d) - c


def decompose(rows0: list[BridgeRow], rows1: list[BridgeRow]) -> dict:
    by0 = {r.key: r for r in rows0}
    by1 = {r.key: r for r in rows1}
    per_key = []
    for key in sorted(set(by0) | set(by1), key=str):
        r0, r1 = by0.get(key), by1.get(key)
        e = dict.fromkeys(EFFECTS, 0.0)
        if r0 and r1 and r0.quantity > 0 and r1.quantity > 0:
            p0, d0, c0, m0 = _unit(r0)
            p1, d1, c1, _m1 = _unit(r1)
            q0, q1 = r0.quantity, r1.quantity
            e["volume"] = (q1 - q0) * m0
            e["price"] = q1 * (p1 - p0) * (1 - d0)
            e["discount"] = q1 * p1 * (d0 - d1)
            e["cost"] = -q1 * (c1 - c0)
        else:
            e["volume"] = (r1.margin if r1 else 0.0) - (r0.margin if r0 else 0.0)
        attrs = (r1.attrs if r1 and r1.attrs else (r0.attrs if r0 else None)) or {}
        per_key.append({"key": key, "attrs": attrs, **e,
                        "margin0": r0.margin if r0 else 0.0, "margin1": r1.margin if r1 else 0.0})
    m0 = sum(r.margin for r in rows0)
    m1 = sum(r.margin for r in rows1)
    rev0 = sum(r.revenue for r in rows0)
    rev1 = sum(r.revenue for r in rows1)
    totals = {k: sum(x[k] for x in per_key) for k in EFFECTS}
    return {
        "margin0": m0,
        "margin1": m1,
        "revenue0": rev0,
        "revenue1": rev1,
        "margin_pct0": m0 / rev0 if rev0 else None,
        "margin_pct1": m1 / rev1 if rev1 else None,
        "effects": totals,
        "residual": (m1 - m0) - sum(totals.values()),
        "per_key": per_key,
    }


def aggregate_effects(per_key: list[dict], dim: str, top: int = 8) -> list[dict]:
    """Soma os efeitos por uma dimensão (ex.: product_line, salesperson_id)."""
    agg: dict[str, dict] = defaultdict(lambda: dict.fromkeys(EFFECTS, 0.0) | {"delta": 0.0})
    for row in per_key:
        name = row["attrs"].get(dim) or "—"
        for k in EFFECTS:
            agg[name][k] += row[k]
        agg[name]["delta"] += row["margin1"] - row["margin0"]
    out = [{"name": k, **v} for k, v in agg.items()]
    out.sort(key=lambda x: x["delta"])
    return out[:top] if top else out
