"""Acesso ao PostgreSQL: pool de conexões e consultas somente leitura, parametrizadas."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pool: ConnectionPool | None = None


class DatabaseUnavailable(RuntimeError):
    pass


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().conninfo, min_size=1, max_size=8, open=True, timeout=5,
            kwargs={"row_factory": dict_row, "autocommit": True,
                    # a API só lê: garante no nível da sessão
                    "options": "-c default_transaction_read_only=on -c statement_timeout=15000"},
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _clean(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    return v


def query(sql: str, params: Sequence[Any] | dict | None = None) -> list[dict]:
    try:
        with get_pool().connection() as conn:
            rows = conn.execute(sql, params).fetchall()
    except Exception as exc:  # noqa: BLE001
        from psycopg import OperationalError
        from psycopg_pool import PoolTimeout

        if isinstance(exc, (OperationalError, PoolTimeout)):
            raise DatabaseUnavailable(str(exc)) from exc
        raise
    return [{k: _clean(v) for k, v in r.items()} for r in rows]


def query_one(sql: str, params: Sequence[Any] | dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
