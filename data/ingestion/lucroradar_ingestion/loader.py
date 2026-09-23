"""Carga de lotes CSV para a camada raw.

Garantias:
- Raw preserva o dado recebido: todas as colunas como texto, sem limpeza.
- Cada linha carrega lote, arquivo, número da linha e hash do conteúdo.
- Reexecução sem duplicação: um arquivo (lote + tabela) com o mesmo SHA-256
  já registrado em `audit.load_files` é ignorado. Arquivo diferente para o
  mesmo lote só é recarregado com `replace=True` (apaga e recarrega na mesma
  transação).
- Linhas com número de colunas diferente do cabeçalho vão para
  `audit.ingestion_rejects` e não entram no raw.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg import sql

from .contracts import SOURCE_CONTRACTS

SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def conninfo_from_env() -> str:
    """Conexão da carga. DATABASE_URL (ex.: banco gerenciado com TLS) tem precedência."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return psycopg.conninfo.make_conninfo(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "lucroradar"),
        password=os.getenv("POSTGRES_PASSWORD", "lucroradar"),
        dbname=os.getenv("POSTGRES_DB", "lucroradar"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
    )


def export_dbt_env_from_url() -> None:
    """Traduz DATABASE_URL para as variáveis POSTGRES_* lidas pelo profiles.yml do dbt."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return
    d = psycopg.conninfo.conninfo_to_dict(url)
    mapping = {"host": "POSTGRES_HOST", "port": "POSTGRES_PORT", "user": "POSTGRES_USER",
               "password": "POSTGRES_PASSWORD", "dbname": "POSTGRES_DB", "sslmode": "POSTGRES_SSLMODE"}
    for key, env in mapping.items():
        if d.get(key):
            os.environ[env] = str(d[key])


class ContractError(RuntimeError):
    pass


@dataclass
class FileResult:
    table: str
    status: str  # loaded | skipped | replaced
    rows: int = 0
    rejected: int = 0


@dataclass
class BatchResult:
    batch_id: str
    files: list[FileResult] = field(default_factory=list)

    @property
    def rows_loaded(self) -> int:
        return sum(f.rows for f in self.files if f.status != "skipped")

    @property
    def rows_rejected(self) -> int:
        return sum(f.rejected for f in self.files if f.status != "skipped")


def ensure_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    for table, cols in SOURCE_CONTRACTS.items():
        col_defs = sql.SQL(", ").join(
            sql.SQL("{} text").format(sql.Identifier(c)) for c in cols
        )
        conn.execute(sql.SQL(
            "CREATE TABLE IF NOT EXISTS raw.{t} ({cols}, "
            "_batch_id text NOT NULL, _source_file text NOT NULL, "
            "_row_number integer NOT NULL, _record_hash text NOT NULL, "
            "_loaded_at timestamptz NOT NULL DEFAULT now(), "
            "PRIMARY KEY (_batch_id, _row_number))"
        ).format(t=sql.Identifier(table), cols=col_defs))
    conn.commit()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_batches(landing: Path) -> list[Path]:
    return sorted(p for p in landing.iterdir() if p.is_dir() and (p / "_batch.json").exists())


def load_batch(conn: psycopg.Connection, batch_dir: Path, replace: bool = False) -> BatchResult:
    meta = json.loads((batch_dir / "_batch.json").read_text(encoding="utf-8"))
    batch_id = meta["batch_name"]
    batch_seq = int(batch_id.split("_")[1])
    result = BatchResult(batch_id)
    with conn.transaction():
        conn.execute(
            """
            INSERT INTO audit.load_batches (batch_id, batch_seq, as_of_date, window_start,
                reference_date, seed, is_synthetic, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'loading')
            ON CONFLICT (batch_id) DO UPDATE SET status = 'loading', finished_at = NULL
            """,
            (batch_id, batch_seq, meta["as_of_date"], meta["window_start"],
             meta["reference_date"], meta.get("seed"), meta.get("synthetic", True)),
        )
    try:
        for table in SOURCE_CONTRACTS:
            path = batch_dir / f"{table}.csv"
            if not path.exists():
                raise ContractError(f"{batch_id}: arquivo ausente {path.name}")
            result.files.append(_load_file(conn, batch_id, table, path, replace))
    except Exception:
        with conn.transaction():
            conn.execute("UPDATE audit.load_batches SET status='failed', finished_at=now() "
                         "WHERE batch_id=%s", (batch_id,))
        raise
    with conn.transaction():
        totals = conn.execute(
            "SELECT coalesce(sum(rows_loaded),0), coalesce(sum(rows_rejected),0) "
            "FROM audit.load_files WHERE batch_id=%s", (batch_id,)).fetchone()
        conn.execute(
            "UPDATE audit.load_batches SET status='loaded', rows_loaded=%s, rows_rejected=%s, "
            "finished_at=now() WHERE batch_id=%s", (totals[0], totals[1], batch_id))
    return result


def _load_file(conn: psycopg.Connection, batch_id: str, table: str, path: Path,
               replace: bool) -> FileResult:
    digest = _sha256(path)
    expected_cols = SOURCE_CONTRACTS[table]
    with conn.transaction():
        prev = conn.execute(
            "SELECT file_sha256 FROM audit.load_files WHERE batch_id=%s AND table_name=%s",
            (batch_id, table)).fetchone()
        status = "loaded"
        if prev is not None:
            if prev[0] == digest:
                return FileResult(table, "skipped")
            if not replace:
                raise ContractError(
                    f"{batch_id}/{table}: arquivo diferente do já carregado "
                    f"(use --replace para recarregar o lote)")
            conn.execute(sql.SQL("DELETE FROM raw.{} WHERE _batch_id=%s").format(
                sql.Identifier(table)), (batch_id,))
            conn.execute("DELETE FROM audit.ingestion_rejects WHERE batch_id=%s AND table_name=%s",
                         (batch_id, table))
            conn.execute("DELETE FROM audit.load_files WHERE batch_id=%s AND table_name=%s",
                         (batch_id, table))
            status = "replaced"

        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header != expected_cols:
                raise ContractError(
                    f"{batch_id}/{table}: cabeçalho {header} difere do contrato {expected_cols}")
            buf = io.StringIO()
            writer = csv.writer(buf)
            rows = rejected = 0
            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(expected_cols):
                    rejected += 1
                    conn.execute(
                        "INSERT INTO audit.ingestion_rejects (batch_id, table_name, row_number, "
                        "reason, raw_line) VALUES (%s,%s,%s,%s,%s)",
                        (batch_id, table, row_number,
                         f"{len(row)} colunas; esperado {len(expected_cols)}", ",".join(row)))
                    continue
                record_hash = hashlib.md5("\x1f".join(row).encode()).hexdigest()
                writer.writerow([*row, batch_id, path.name, row_number, record_hash])
                rows += 1
        cols = [*expected_cols, "_batch_id", "_source_file", "_row_number", "_record_hash"]
        copy_sql = sql.SQL("COPY raw.{t} ({c}) FROM STDIN WITH (FORMAT csv)").format(
            t=sql.Identifier(table), c=sql.SQL(", ").join(sql.Identifier(c) for c in cols))
        with conn.cursor().copy(copy_sql) as copy:
            copy.write(buf.getvalue())
        conn.execute(
            "INSERT INTO audit.load_files (batch_id, table_name, file_name, file_sha256, "
            "rows_loaded, rows_rejected) VALUES (%s,%s,%s,%s,%s,%s)",
            (batch_id, table, path.name, digest, rows, rejected))
    return FileResult(table, status, rows, rejected)
