from datetime import date

import pytest
from lucroradar_api.filters import FilterError, Period, build_filters

W = (date(2025, 1, 1), date(2026, 6, 1))


def test_defaults_and_previous_period():
    f = build_filters(start=None, end=None, window=W, default_months=6)
    assert f.period == Period(date(2026, 1, 1), date(2026, 6, 1))
    assert f.comparison_period() == Period(date(2025, 7, 1), date(2025, 12, 1))


def test_yoy_comparison():
    f = build_filters(start="2026-04", end="2026-06", compare="yoy", window=W)
    assert f.comparison_period() == Period(date(2025, 4, 1), date(2025, 6, 1))


@pytest.mark.parametrize("kw", [
    {"start": "2024-12", "end": "2025-02"},
    {"start": "2026-05", "end": "2026-02"},
    {"start": "2026-13", "end": None},
    {"start": None, "end": None, "business_line": "leasing"},
    {"start": None, "end": None, "segment": "Mineração"},
])
def test_invalid_filters_rejected(kw):
    with pytest.raises(FilterError):
        build_filters(window=W, options={"segment": ["Construção"]}, **kw)


def test_where_is_parameterized_and_respects_applicability():
    f = build_filters(start="2026-01", end="2026-03", segment="Construção'; drop table x;--",
                      product_line="Geradores", window=W)
    sql, params = f.where("receivables")
    assert "drop" not in sql and "segment = %s" in sql
    assert "product_line" not in sql
    assert f.not_applied("receivables") == ["linha de produto"]
    assert params[-1] == "Construção'; drop table x;--"
