"""Avaliação AO VIVO do copiloto com modelo generativo (requer ANTHROPIC_API_KEY).

Uso:  ANTHROPIC_API_KEY=... uv run python tests/evals/run_llm_evals.py
Custo: ~6 perguntas × poucas chamadas de ferramenta. Não roda em CI por padrão.

Critérios por pergunta (resultado conhecido pelo manifesto do gerador):
- fidelidade numérica: nenhum número no resumo sem evidência correspondente;
- respeito aos filtros: filtros usados pelas ferramentas contêm os filtros da tela;
- evidência: ao menos uma evidência citada e o fato esperado presente nas evidências;
- causalidade: resumo não usa linguagem causal forte ("causou", "comprova").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from lucroradar_api import metrics
from lucroradar_api.config import get_settings
from lucroradar_api.copilot.providers import AnthropicProvider, CopilotError
from lucroradar_api.filters import build_filters

MANIFEST = json.loads((Path(__file__).resolve().parents[2] / "data/manifest/ground_truth.json").read_text())
SC = MANIFEST["scenarios"]

CASES = [
    {"q": "Por que a margem de contribuição caiu se a receita cresceu?", "filters": {}, "expect_any": ["Desconto", "Custo"]},
    {"q": "Quais vendedores mais pressionaram a margem com desconto?", "filters": {}, "expect_any": SC["discount_escalation"]["salesperson_ids"]},
    {"q": "Quais clientes explicam o aumento dos vencidos?", "filters": {}, "expect_any": SC["late_payments"]["customer_ids"]},
    {"q": "Qual equipamento está mais ocioso?", "filters": {}, "expect_any": [SC["idle_fleet"]["sku"]]},
    {"q": "Qual etapa dos pedidos ficou mais lenta?", "filters": {}, "expect_any": ["crédito"]},
    {"q": "Como está a margem?", "filters": {"segment": "Eventos"}, "expect_any": ["Margem"]},
]
CAUSAL = re.compile(r"\b(causou|causaram|comprova|comprovadamente)\b", re.I)


def main() -> int:
    s = get_settings()
    if not s.llm_enabled:
        print("ANTHROPIC_API_KEY ausente: avaliação ao vivo não executada.")
        return 2
    meta = metrics.get_meta()
    provider = AnthropicProvider(s)
    failures = 0
    for case in CASES:
        f = build_filters(start="2026-01", end="2026-06", options=meta["options"],
                          window=(meta["window_start"], meta["window_end"]), **case["filters"])
        try:
            a = provider.answer(case["q"], f)
        except CopilotError as exc:
            print(f"ERRO  {case['q']}: {exc}")
            failures += 1
            continue
        text = " ".join(e["label"] + " " + e["formatted"] for e in a["evidence"])
        checks = {
            "numeros_com_evidencia": not a["unsupported_numbers"],
            "tem_evidencia": bool(a["evidence"]),
            "fato_esperado": any(x.lower() in text.lower() for x in case["expect_any"]),
            "filtros": all(all(u.get(k) == v for k, v in case["filters"].items()) for u in a["filters_used"]),
            "sem_causalidade_forte": not CAUSAL.search(a["summary"]),
        }
        ok = all(checks.values())
        failures += not ok
        print(f"{'OK  ' if ok else 'FALHA'} {case['q']} {checks}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} perguntas aprovadas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
