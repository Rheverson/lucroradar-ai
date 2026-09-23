"""Integração com o SDK oficial da Anthropic sem rede e sem chave real.

O transporte HTTP é simulado: verifica o formato da requisição enviada pelo SDK
(modelo, ferramentas, beta de fallback, ausência de SQL) e o parsing das respostas
de tool use pelo próprio SDK. Não substitui a avaliação com o provedor real.
"""

import json

import pytest

pytestmark = pytest.mark.db


def _msg(content, stop="tool_use"):
    return {"id": "msg_x", "type": "message", "role": "assistant", "model": "claude-opus-5",
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10}}


def test_anthropic_sdk_request_and_parsing(monkeypatch):
    import anthropic
    import httpx2
    from lucroradar_api import metrics
    from lucroradar_api.config import Settings
    from lucroradar_api.copilot.providers import AnthropicProvider
    from lucroradar_api.filters import build_filters

    sent = []
    script = [
        _msg([{"type": "tool_use", "id": "t1", "name": "get_kpi_summary", "input": {}}]),
        _msg([{"type": "tool_use", "id": "t2", "name": "submit_answer",
               "input": {"summary": "A margem caiu; ver E3.", "evidence_ids": ["E1", "E3"],
                         "limitations": ["teste offline"]}}]),
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
        return httpx2.Response(200, json=script[len(sent) - 1])

    settings = Settings(anthropic_api_key="chave-de-teste-offline")
    p = AnthropicProvider(settings)
    p.client = anthropic.Anthropic(api_key="chave-de-teste-offline", max_retries=0,
                                   http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    m = metrics.get_meta()
    f = build_filters(start="2026-01", end="2026-06", options=m["options"],
                      window=(m["window_start"], m["window_end"]))
    a = p.answer("Por que a margem caiu?", f)

    assert len(sent) == 2
    first = sent[0]
    assert first["url"].endswith("/v1/messages?beta=true") or first["url"].endswith("/v1/messages")
    assert first["body"]["model"] == settings.copilot_model
    assert first["body"]["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in first["headers"].get("anthropic-beta", "")
    assert {t["name"] for t in first["body"]["tools"]} >= {"get_kpi_summary", "submit_answer"}
    assert "select " not in json.dumps(first["body"]["tools"]).lower()
    # o resultado da ferramenta volta ao modelo no segundo turno
    tool_result = sent[1]["body"]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"
    assert a["mode"] == "llm" and [e["id"] for e in a["evidence"]] == ["E1", "E3"]
    assert a["unsupported_numbers"] == []


def test_anthropic_sdk_errors_are_mapped(monkeypatch):
    import anthropic
    import httpx2
    from lucroradar_api import metrics
    from lucroradar_api.config import Settings
    from lucroradar_api.copilot.providers import AnthropicProvider, CopilotError
    from lucroradar_api.filters import build_filters

    m = metrics.get_meta()
    f = build_filters(start="2026-01", end="2026-06", options=m["options"],
                      window=(m["window_start"], m["window_end"]))
    for status, expected in ((401, 502), (429, 429), (500, 502)):
        def handler(request, status=status):
            return httpx2.Response(status, json={"type": "error", "error": {"type": "x", "message": "detalhe interno"}})

        p = AnthropicProvider(Settings(anthropic_api_key="chave-de-teste-offline"))
        p.client = anthropic.Anthropic(api_key="chave-de-teste-offline", max_retries=0,
                                       http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
        with pytest.raises(CopilotError) as e:
            p.answer("teste", f)
        assert e.value.status == expected
        assert "detalhe interno" not in str(e.value)
