"""Preparação para exposição pública: erros sem detalhes, limites do copiloto e configuração."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from lucroradar_api.config import Settings
from lucroradar_api.routers import copilot as copilot_router


def test_production_refuses_default_db_password():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", postgres_password="lucroradar").validate_for_runtime()
    Settings(app_env="production", postgres_password="uma-senha-forte").validate_for_runtime()
    Settings(app_env="development", postgres_password="lucroradar").validate_for_runtime()


def test_forwarded_for_only_when_trusted(monkeypatch):
    req = SimpleNamespace(headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, client=SimpleNamespace(host="10.0.0.2"))
    monkeypatch.setattr(copilot_router, "get_settings", lambda: Settings(trust_forwarded_for=False))
    assert copilot_router.client_ip(req) == "10.0.0.2"
    monkeypatch.setattr(copilot_router, "get_settings", lambda: Settings(trust_forwarded_for=True))
    assert copilot_router.client_ip(req) == "203.0.113.9"


def test_copilot_limits_per_ip_and_daily(monkeypatch):
    monkeypatch.setattr(copilot_router, "get_settings",
                        lambda: Settings(copilot_requests_per_minute=2, copilot_daily_limit=3))
    copilot_router._hits.clear()
    copilot_router._daily["count"] = 0
    copilot_router.enforce_llm_limits("a")
    copilot_router.enforce_llm_limits("a")
    with pytest.raises(HTTPException) as e:
        copilot_router.enforce_llm_limits("a")
    assert e.value.status_code == 429
    copilot_router.enforce_llm_limits("b")  # 3ª pergunta do dia
    with pytest.raises(HTTPException) as e:
        copilot_router.enforce_llm_limits("c")
    assert "diário" in e.value.detail
    copilot_router._hits.clear()
    copilot_router._daily["count"] = 0


@pytest.mark.db
def test_unexpected_errors_hide_internal_details(monkeypatch):
    from fastapi.testclient import TestClient
    from lucroradar_api import metrics
    from lucroradar_api.main import app

    client = TestClient(app, raise_server_exceptions=False)

    def boom(*a, **k):
        raise RuntimeError("segredo interno: postgresql://usuario:senha@host")

    monkeypatch.setattr(metrics, "kpi_summary", boom)
    r = client.get("/api/v1/executive/summary", params={"start": "2026-01", "end": "2026-06"})
    assert r.status_code == 500
    assert "segredo" not in r.text and "postgresql" not in r.text
    assert r.json()["error_id"]


@pytest.mark.db
def test_meta_and_status_do_not_expose_credentials(client):
    for path in ("/api/v1/meta", "/api/v1/copilot/status", "/api/health"):
        body = client.get(path).text.lower()
        assert "password" not in body and "api_key" not in body and "sk-ant" not in body
