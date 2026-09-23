"""CLI do pipeline.

    lucroradar-ingest load            # carrega lotes pendentes de data/landing
    lucroradar-ingest run             # schema + carga + dbt build, com log em audit.*
    lucroradar-ingest run --generate  # gera os dados sintéticos antes
    lucroradar-ingest status          # últimas execuções e lotes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from .loader import (
    conninfo_from_env,
    discover_batches,
    ensure_schema,
    export_dbt_env_from_url,
    load_batch,
)

ROOT = Path(__file__).resolve().parents[3]
DBT_DIR = ROOT / "analytics" / "dbt"


class RunLog:
    """Registra passos de uma execução em audit.pipeline_runs / pipeline_run_steps."""

    def __init__(self, conn: psycopg.Connection, trigger: str):
        self.conn = conn
        self.run_id = conn.execute(
            "INSERT INTO audit.pipeline_runs (trigger, status) VALUES (%s, 'running') RETURNING run_id",
            (trigger,)).fetchone()[0]
        self.step = 0

    def start(self, name: str) -> int:
        self.step += 1
        self.conn.execute(
            "INSERT INTO audit.pipeline_run_steps (run_id, step_order, step_name, status) "
            "VALUES (%s,%s,%s,'running')", (self.run_id, self.step, name))
        print(f"[{self.run_id}.{self.step}] {name}...", flush=True)
        return self.step

    def finish(self, step: int, status: str, rows: int | None = None, detail: str | None = None) -> None:
        self.conn.execute(
            "UPDATE audit.pipeline_run_steps SET status=%s, rows_affected=%s, detail=%s, "
            "finished_at=now() WHERE run_id=%s AND step_order=%s",
            (status, rows, detail, self.run_id, step))
        print(f"    -> {status}" + (f" ({rows} linhas)" if rows is not None else "")
              + (f" — {detail}" if detail else ""), flush=True)

    def close(self, status: str, message: str | None = None) -> None:
        self.conn.execute(
            "UPDATE audit.pipeline_runs SET status=%s, message=%s, finished_at=now() WHERE run_id=%s",
            (status, message, self.run_id))


READER_SCHEMAS = ("raw", "staging", "intermediate", "marts", "quality", "audit", "reference", "util")


def grant_reader(conn: psycopg.Connection, role: str) -> None:
    """Somente leitura para o papel usado pela API; a carga continua com o papel dono."""
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    if not exists:
        raise SystemExit(f"Papel '{role}' não existe. Crie-o no painel do banco e rode novamente.")
    r = sql.Identifier(role)
    schemas = [s for (s,) in conn.execute(
        "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)", (list(READER_SCHEMAS),))]
    for name in schemas:
        n = sql.Identifier(name)
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(n, r))
        conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(n, r))
        conn.execute(sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}").format(n, r))
        conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}").format(n, r))
    conn.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(r))
    print(f"Leitura concedida a {role} em: {', '.join(sorted(schemas))}")


def run_dbt(args: list[str]) -> tuple[bool, str]:
    from dbt.cli.main import dbtRunner

    os.environ.setdefault("DBT_PROFILES_DIR", str(DBT_DIR))
    export_dbt_env_from_url()
    res = dbtRunner().invoke([*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)])
    detail = ""
    if res.result is not None and hasattr(res.result, "results"):
        statuses: dict[str, int] = {}
        for r in res.result.results:
            statuses[str(r.status)] = statuses.get(str(r.status), 0) + 1
        detail = ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
    if res.exception:
        detail = f"{detail} erro: {res.exception}".strip()
    return res.success, detail


def cmd_load(conn: psycopg.Connection, landing: Path, replace: bool, log: RunLog | None) -> int:
    ensure_schema(conn)
    total = 0
    for bdir in discover_batches(landing):
        step = log.start(f"ingestao:{bdir.name}") if log else None
        res = load_batch(conn, bdir, replace=replace)
        skipped = sum(1 for f in res.files if f.status == "skipped")
        detail = f"{len(res.files) - skipped} arquivos carregados, {skipped} já existentes (ignorados)"
        if res.rows_rejected:
            detail += f", {res.rows_rejected} linhas rejeitadas"
        if log:
            log.finish(step, "success" if skipped < len(res.files) else "skipped",
                       res.rows_loaded, detail)
        else:
            print(f"{bdir.name}: {res.rows_loaded} linhas; {detail}")
        total += res.rows_loaded
    return total


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Pipeline LucroRadar AI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_load = sub.add_parser("load")
    p_load.add_argument("--landing", type=Path, default=ROOT / "data" / "landing")
    p_load.add_argument("--replace", action="store_true")
    p_run = sub.add_parser("run")
    p_run.add_argument("--landing", type=Path, default=ROOT / "data" / "landing")
    p_run.add_argument("--generate", action="store_true", help="gera dados sintéticos antes")
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--reference-date", default="2026-06-30")
    p_run.add_argument("--replace", action="store_true")
    p_run.add_argument("--skip-dbt", action="store_true")
    p_run.add_argument("--trigger", default="manual")
    sub.add_parser("status")
    p_grant = sub.add_parser("grant-reader", help="concede leitura dos esquemas a um papel já existente")
    p_grant.add_argument("--role", default="lucroradar_reader")
    args = ap.parse_args(argv)

    with psycopg.connect(conninfo_from_env(), autocommit=True) as conn:
        if args.cmd == "load":
            cmd_load(conn, args.landing, args.replace, None)
            return
        if args.cmd == "grant-reader":
            grant_reader(conn, args.role)
            return
        if args.cmd == "status":
            ensure_schema(conn)
            for r in conn.execute(
                    "SELECT run_id, status, started_at, finished_at, message FROM audit.pipeline_runs "
                    "ORDER BY run_id DESC LIMIT 5"):
                print(r)
            for r in conn.execute("SELECT batch_id, status, rows_loaded, rows_rejected "
                                  "FROM audit.load_batches ORDER BY batch_seq"):
                print(r)
            return
        ensure_schema(conn)
        log = RunLog(conn, args.trigger)
        try:
            if args.generate:
                from datetime import date

                from lucroradar_generator.config import GeneratorConfig
                from lucroradar_generator.writer import write_dataset

                step = log.start("gerar_dados_sinteticos")
                cfg = GeneratorConfig(seed=args.seed,
                                      reference_date=date.fromisoformat(args.reference_date))
                m = write_dataset(cfg, args.landing, ROOT / "data" / "manifest")
                rows = sum(sum(t.values()) for t in m["batches"].values())
                log.finish(step, "success", rows, f"seed={cfg.seed}, referência={cfg.reference_date}")
            cmd_load(conn, args.landing, args.replace, log)
            if not args.skip_dbt:
                step = log.start("dbt_build")
                ok, detail = run_dbt(["build"])
                log.finish(step, "success" if ok else "failed", None, detail)
                if not ok:
                    raise RuntimeError(f"dbt build falhou: {detail}")
            log.close("success")
            print(f"Execução {log.run_id} concluída.")
        except Exception as exc:  # registra e propaga
            log.close("failed", str(exc)[:1000])
            print(f"Execução {log.run_id} falhou: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
