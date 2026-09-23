-- Esquemas de controle e camada raw do LucroRadar AI.
-- Idempotente: pode ser executado várias vezes.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Lote recebido (uma pasta com CSVs + _batch.json)
CREATE TABLE IF NOT EXISTS audit.load_batches (
    batch_id        text PRIMARY KEY,
    batch_seq       integer NOT NULL UNIQUE,
    as_of_date      date NOT NULL,
    window_start    date NOT NULL,
    reference_date  date NOT NULL,
    seed            integer,
    is_synthetic    boolean NOT NULL DEFAULT true,
    status          text NOT NULL CHECK (status IN ('loading', 'loaded', 'failed')),
    rows_loaded     integer NOT NULL DEFAULT 0,
    rows_rejected   integer NOT NULL DEFAULT 0,
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz
);

-- Arquivo carregado dentro de um lote: o hash garante reexecução sem duplicar
CREATE TABLE IF NOT EXISTS audit.load_files (
    batch_id     text NOT NULL REFERENCES audit.load_batches(batch_id),
    table_name   text NOT NULL,
    file_name    text NOT NULL,
    file_sha256  text NOT NULL,
    rows_loaded  integer NOT NULL,
    rows_rejected integer NOT NULL DEFAULT 0,
    loaded_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, table_name)
);

-- Linhas estruturalmente inválidas (nº de colunas errado): nunca entram no raw
CREATE TABLE IF NOT EXISTS audit.ingestion_rejects (
    batch_id    text NOT NULL,
    table_name  text NOT NULL,
    row_number  integer NOT NULL,
    reason      text NOT NULL,
    raw_line    text,
    rejected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, table_name, row_number)
);

-- Execuções do pipeline (ingestão + dbt) e seus passos
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id       bigserial PRIMARY KEY,
    trigger      text NOT NULL DEFAULT 'manual',
    status       text NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    message      text
);

CREATE TABLE IF NOT EXISTS audit.pipeline_run_steps (
    run_id       bigint NOT NULL REFERENCES audit.pipeline_runs(run_id),
    step_order   integer NOT NULL,
    step_name    text NOT NULL,
    status       text NOT NULL CHECK (status IN ('running', 'success', 'skipped', 'failed')),
    rows_affected integer,
    detail       text,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    PRIMARY KEY (run_id, step_order)
);
