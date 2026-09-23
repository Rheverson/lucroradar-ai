import json
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "manifest" / "ground_truth.json"


def _db_ready() -> bool:
    try:
        from lucroradar_ingestion.loader import conninfo_from_env

        with psycopg.connect(conninfo_from_env(), connect_timeout=3) as c:
            return c.execute("select to_regclass('marts.mart_contribution_monthly') is not null").fetchone()[0]
    except Exception:
        return False


DB_READY = _db_ready()


def pytest_collection_modifyitems(config, items):
    if DB_READY:
        return
    skip = pytest.mark.skip(reason="PostgreSQL com pipeline executado indisponível (rode `make pipeline`)")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def manifest() -> dict:
    if not MANIFEST.exists():
        pytest.skip("Manifesto ausente: rode o gerador")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def db():
    from lucroradar_ingestion.loader import conninfo_from_env

    with psycopg.connect(conninfo_from_env(), autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from lucroradar_api.main import app

    with TestClient(app) as c:
        yield c
