from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date


def add_months(d: date, months: int) -> date:
    """Soma meses mantendo o dia 1 quando possível (usado para janelas mensais)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


@dataclass(frozen=True)
class GeneratorConfig:
    """Parâmetros do gerador. Mesmo seed + mesma data de referência = mesmos arquivos."""

    seed: int = 42
    reference_date: date = date(2026, 6, 30)
    months: int = 18
    # Escala de volume (1.0 ≈ 3,5 mil pedidos de venda e 1,6 mil contratos)
    scale: float = 1.0
    extra: dict = field(default_factory=dict)

    @property
    def window_start(self) -> date:
        first_of_ref_month = self.reference_date.replace(day=1)
        return add_months(first_of_ref_month, -(self.months - 1))

    @property
    def incremental_cutoff(self) -> date:
        """Primeiro dia do mês de referência: o lote incremental traz esse mês."""
        return self.reference_date.replace(day=1)
