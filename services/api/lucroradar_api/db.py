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


def _configure(conn) -> None:
    # A API só lê: garante no nível da sessão (além do usuário somente leitura em produção).
    # SET em vez de "options" na conexão: compatível com poolers (ex.: PgBouncer do Neon).
    conn.execute("SET default_transaction_read_only = on")
    conn.execute("SET statement_timeout = '15s'")


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ConnectionPool(
            s.conninfo, min_size=0, max_size=s.db_pool_max_size, open=True, timeout=20,
            max_idle=60, configure=_configure,
            # prepare_threshold=None: sem prepared statements (seguro atrás de pooler em modo transação)
            kwargs={"row_factory": dict_row, "autocommit": True, "prepare_threshold": None,
                    "connect_timeout": 15},
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
