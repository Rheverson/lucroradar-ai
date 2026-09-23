"""Filtros compartilhados (período, linha de negócio, segmento, região, linha de produto).

Toda cláusula SQL é montada a partir de uma lista fechada de colunas e com
parâmetros vinculados. Valores de texto são validados contra as opções
existentes no banco.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from datetime import date

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
BUSINESS_LINES = {"sale": "Venda", "rental": "Locação"}

# dimensão → coluna nas tabelas de fato
DIMENSIONS = ("business_line", "segment", "region", "product_line")

# Quais filtros fazem sentido em cada conjunto de dados
APPLICABILITY = {
    "contribution": {"business_line", "segment", "region", "product_line"},
    "receivables": {"business_line", "segment", "region"},
    "fleet": {"product_line"},
    "orders": {"business_line", "segment", "region"},
}

FILTER_LABELS = {
    "business_line": "linha de negócio",
    "segment": "segmento",
    "region": "região",
    "product_line": "linha de produto",
}


class FilterError(ValueError):
    pass


def parse_month(s: str) -> date:
    if not MONTH_RE.match(s or ""):
        raise FilterError(f"Mês inválido: {s!r} (use AAAA-MM)")
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_label(d: date) -> str:
    names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{names[d.month - 1]}/{d.year}"


@dataclass(frozen=True)
class Period:
    start: date  # primeiro dia do mês inicial
    end: date  # primeiro dia do mês final (inclusivo)

    @property
    def months(self) -> int:
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1

    @property
    def end_exclusive(self) -> date:
        return add_months(self.end, 1)

    def previous(self) -> Period:
        return Period(add_months(self.start, -self.months), add_months(self.end, -self.months))

    def year_ago(self) -> Period:
        return Period(add_months(self.start, -12), add_months(self.end, -12))

    @property
    def label(self) -> str:
        if self.start == self.end:
            return month_label(self.start)
        return f"{month_label(self.start)} a {month_label(self.end)}"

    def to_dict(self) -> dict:
        return {"start": self.start.strftime("%Y-%m"), "end": self.end.strftime("%Y-%m"),
                "label": self.label, "months": self.months}


@dataclass(frozen=True)
class Filters:
    period: Period
    business_line: str | None = None
    segment: str | None = None
    region: str | None = None
    product_line: str | None = None
    compare: str = "previous"  # previous | yoy
    extra: dict = field(default_factory=dict)

    def dims(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in DIMENSIONS if getattr(self, k)}

    def comparison_period(self) -> Period:
        return self.period.year_ago() if self.compare == "yoy" else self.period.previous()

    def with_period(self, period: Period) -> Filters:
        return replace(self, period=period)

    def where(self, dataset: str, alias: str = "", month_col: str = "month_start",
              period: Period | None = None, colmap: dict | None = None,
              skip: set[str] | None = None) -> tuple[str, list]:
        """Cláusula WHERE com período e dimensões aplicáveis ao conjunto de dados."""
        p = period or self.period
        a = f"{alias}." if alias else ""
        clauses = [f"{a}{month_col} >= %s", f"{a}{month_col} < %s"]
        params: list = [p.start, p.end_exclusive]
        dim_sql, dim_params = self.dims_where(dataset, alias, colmap, skip)
        return " and ".join([*clauses, dim_sql]), params + dim_params

    def dims_where(self, dataset: str, alias: str = "", colmap: dict | None = None,
                   skip: set[str] | None = None) -> tuple[str, list]:
        a = f"{alias}." if alias else ""
        clauses, params = ["true"], []
        for dim, value in self.dims().items():
            if dim in APPLICABILITY[dataset] and dim not in (skip or set()):
                col = (colmap or {}).get(dim, dim)
                clauses.append(f"{a}{col} = %s")
                params.append(value)
        return " and ".join(clauses), params

    def not_applied(self, dataset: str) -> list[str]:
        return [FILTER_LABELS[d] for d in self.dims() if d not in APPLICABILITY[dataset]]

    def describe(self) -> dict:
        d = {"period": self.period.to_dict(), "comparison": self.comparison_period().to_dict(),
             "compare_mode": self.compare}
        d.update({k: v for k, v in asdict(self).items() if k in DIMENSIONS and v})
        if self.business_line:
            d["business_line_label"] = BUSINESS_LINES.get(self.business_line, self.business_line)
        return d

    def human(self) -> str:
        parts = [self.period.label]
        for dim, value in self.dims().items():
            label = BUSINESS_LINES.get(value, value) if dim == "business_line" else value
            parts.append(f"{FILTER_LABELS[dim]}: {label}")
        return " · ".join(parts)


def build_filters(*, start: str | None, end: str | None, business_line: str | None = None,
                  segment: str | None = None, region: str | None = None,
                  product_line: str | None = None, compare: str = "previous",
                  options: dict | None = None, window: tuple[date, date] | None = None,
                  default_months: int = 3) -> Filters:
    """Valida e normaliza filtros vindos da URL ou do copiloto."""
    if window is None:
        raise FilterError("Janela de dados indisponível")
    w_start, w_end = window
    end_d = parse_month(end) if end else w_end
    start_d = parse_month(start) if start else add_months(end_d, -(default_months - 1))
    if start_d > end_d:
        raise FilterError("Mês inicial posterior ao final")
    if start_d < w_start or end_d > w_end:
        raise FilterError(
            f"Período fora da janela de dados ({month_label(w_start)} a {month_label(w_end)})")
    if business_line and business_line not in BUSINESS_LINES:
        raise FilterError("Linha de negócio deve ser 'sale' ou 'rental'")
    if compare not in ("previous", "yoy"):
        raise FilterError("Comparação deve ser 'previous' ou 'yoy'")
    opts = options or {}
    for name, value in (("segment", segment), ("region", region), ("product_line", product_line)):
        if value and opts.get(name) is not None and value not in opts[name]:
            raise FilterError(f"Valor desconhecido para {FILTER_LABELS[name]}: {value!r}")
    return Filters(Period(start_d, end_d), business_line or None, segment or None, region or None,
                   product_line or None, compare)
