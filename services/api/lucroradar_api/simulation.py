"""Simulação determinística de cenários operacionais.

Não é previsão estatística nem resultado garantido: aplica premissas explícitas
sobre a base observada do período selecionado.

Alavancas:
- discount_change_pp: variação (pontos percentuais) na taxa de desconto da VENDA.
  Premissa: volume e preço de lista constantes (sem elasticidade).
- utilization_change_pp: variação (p.p.) na utilização da frota de LOCAÇÃO.
  Premissas: receita por unidade-dia locada constante; custo logístico e de
  manutenção proporcionais aos dias locados; utilização limitada a
  `max_utilization` (padrão 95%) e a 0%.
- collection_delay_days: variação no prazo médio de recebimento (dias).
  Efeito de caixa: capital adicional preso em contas a receber ≈ receita diária
  × variação de dias (aproximação de prazo médio de recebimento). Não altera margem.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

MAX_DISCOUNT_CHANGE_PP = 20.0
MAX_UTILIZATION_CHANGE_PP = 40.0
MAX_DELAY_CHANGE_DAYS = 90
DEFAULT_MAX_UTILIZATION = 0.95


class SimulationError(ValueError):
    pass


@dataclass(frozen=True)
class Baseline:
    """Base observada no período (mesmos filtros da análise)."""

    days: int  # dias corridos no período
    sale_gross: float  # receita bruta de venda (preço de lista)
    sale_discount: float  # desconto concedido na venda
    sale_direct_cost: float  # custos diretos da venda (linhas com custo conhecido)
    sale_revenue_cost_known: float  # receita de venda com custo conhecido
    rental_revenue: float
    rental_direct_cost: float  # logística + manutenção
    rental_rented_days: float  # unidade-dia locada
    rental_available_days: float  # unidade-dia disponível (frota − manutenção)
    receipts: float  # recebimentos no período
    open_receivables: float  # saldo em aberto no fim do período
    dso_days: float | None  # prazo médio de recebimento observado

    @property
    def sale_revenue(self) -> float:
        return self.sale_gross - self.sale_discount

    @property
    def cost_coverage(self) -> float:
        return self.sale_revenue_cost_known / self.sale_revenue if self.sale_revenue else 1.0

    @property
    def utilization(self) -> float | None:
        return self.rental_rented_days / self.rental_available_days if self.rental_available_days else None


@dataclass(frozen=True)
class Levers:
    discount_change_pp: float = 0.0
    utilization_change_pp: float = 0.0
    collection_delay_days: float = 0.0
    max_utilization: float = DEFAULT_MAX_UTILIZATION

    def validate(self) -> None:
        if abs(self.discount_change_pp) > MAX_DISCOUNT_CHANGE_PP:
            raise SimulationError(f"Variação de desconto limitada a ±{MAX_DISCOUNT_CHANGE_PP:.0f} p.p.")
        if abs(self.utilization_change_pp) > MAX_UTILIZATION_CHANGE_PP:
            raise SimulationError(f"Variação de utilização limitada a ±{MAX_UTILIZATION_CHANGE_PP:.0f} p.p.")
        if abs(self.collection_delay_days) > MAX_DELAY_CHANGE_DAYS:
            raise SimulationError(f"Variação de prazo limitada a ±{MAX_DELAY_CHANGE_DAYS} dias.")
        if not 0.5 <= self.max_utilization <= 1.0:
            raise SimulationError("Utilização máxima deve estar entre 50% e 100%.")


def _metrics(sale_gross, sale_discount, sale_cost, sale_rev_known_share,
             rental_rev, rental_cost, rented, available, extra_receivables) -> dict:
    sale_rev = sale_gross - sale_discount
    sale_rev_known = sale_rev * sale_rev_known_share
    sale_margin = sale_rev_known - sale_cost
    rental_margin = rental_rev - rental_cost
    revenue = sale_rev + rental_rev
    revenue_known = sale_rev_known + rental_rev
    margin = sale_margin + rental_margin
    return {
        "sale_revenue": sale_rev,
        "sale_discount": sale_discount,
        "sale_discount_rate": sale_discount / sale_gross if sale_gross else None,
        "sale_margin": sale_margin,
        "rental_revenue": rental_rev,
        "rental_margin": rental_margin,
        "rental_utilization": rented / available if available else None,
        "rental_rented_days": rented,
        "revenue": revenue,
        "contribution_margin": margin,
        "margin_pct": margin / revenue_known if revenue_known else None,
        "cash_tied_in_receivables_change": extra_receivables,
    }


def simulate(base: Baseline, levers: Levers) -> dict:
    levers.validate()
    notes: list[str] = []

    # --- base
    known_share = base.cost_coverage
    base_m = _metrics(base.sale_gross, base.sale_discount, base.sale_direct_cost, known_share,
                      base.rental_revenue, base.rental_direct_cost, base.rental_rented_days,
                      base.rental_available_days, 0.0)

    # --- desconto (venda): volume e preço de lista constantes
    base_rate = base.sale_discount / base.sale_gross if base.sale_gross else 0.0
    new_rate = base_rate + levers.discount_change_pp / 100
    if new_rate < 0:
        notes.append("Desconto limitado a 0%.")
        new_rate = 0.0
    if new_rate > 0.9:
        new_rate = 0.9
        notes.append("Desconto limitado a 90%.")
    new_discount = base.sale_gross * new_rate
    # custo das linhas com custo conhecido não muda com desconto
    sale_cost = base.sale_direct_cost

    # --- utilização (locação): limite físico
    rented = base.rental_rented_days
    rental_rev = base.rental_revenue
    rental_cost = base.rental_direct_cost
    if base.rental_available_days and base.utilization is not None:
        target = base.utilization + levers.utilization_change_pp / 100
        cap = levers.max_utilization
        if target > cap:
            notes.append(f"Utilização limitada a {cap:.0%} (capacidade física e giro de manutenção).")
            target = max(cap, base.utilization) if base.utilization > cap else cap
        if target < 0:
            notes.append("Utilização limitada a 0%.")
            target = 0.0
        new_rented = target * base.rental_available_days
        if base.rental_rented_days:
            factor = new_rented / base.rental_rented_days
            rental_rev = base.rental_revenue * factor
            rental_cost = base.rental_direct_cost * factor
        rented = new_rented
    elif levers.utilization_change_pp:
        notes.append("Sem frota disponível no filtro atual: utilização não simulada.")

    # --- prazo de recebimento (caixa)
    daily_revenue = (base.sale_revenue + base.rental_revenue) / base.days if base.days else 0.0
    extra_receivables = daily_revenue * levers.collection_delay_days

    sim_m = _metrics(base.sale_gross, new_discount, sale_cost, known_share, rental_rev, rental_cost,
                     rented, base.rental_available_days, extra_receivables)
    delta = {k: (sim_m[k] - base_m[k]) if isinstance(sim_m[k], (int, float)) and isinstance(base_m[k], (int, float)) else None
             for k in sim_m}
    return {
        "levers": asdict(levers),
        "baseline": base_m,
        "simulated": sim_m,
        "delta": delta,
        "daily_revenue": daily_revenue,
        "notes": notes,
        "assumptions": ASSUMPTIONS,
        "limitations": LIMITATIONS,
        "disclaimer": "Impacto simulado sob premissas explícitas. Não é ganho realizado nem garantido.",
    }


ASSUMPTIONS = [
    "Desconto: volume vendido e preço de lista constantes (sem elasticidade de demanda).",
    "Desconto: margem calculada somente sobre linhas com custo conhecido, como na base.",
    "Utilização: receita e custos diretos por unidade-dia locada constantes.",
    "Utilização: frota e dias em manutenção iguais aos do período base.",
    "Prazo de recebimento: variação de capital em contas a receber ≈ receita diária × dias.",
]

LIMITATIONS = [
    "Não modela reação de clientes, concorrência ou sazonalidade.",
    "Não inclui impostos, despesas fixas nem depreciação: não é lucro líquido.",
    "Prazo de recebimento afeta caixa, não margem; não estima inadimplência.",
    "Resultados dependem da cobertura de custo do período (ver Qualidade dos dados).",
]
