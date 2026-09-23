"""Gera lucroradar-resumo-executivo.json (workflow n8n importável) a partir de check_conditions.js."""

import json
from pathlib import Path

HERE = Path(__file__).parent
logic = (HERE / "check_conditions.js").read_text(encoding="utf-8").split("if (typeof module")[0]

code_node = logic + """
const config = $('Configuração').first().json;
const summary = $input.first().json;
return [{ json: { ...checkConditions(summary, config), config } }];
"""

nodes = [
    {"parameters": {}, "id": "a1", "name": "Executar manualmente", "type": "n8n-nodes-base.manualTrigger",
     "typeVersion": 1, "position": [0, 300]},
    {"parameters": {"assignments": {"assignments": [
        {"id": "c1", "name": "api_url", "type": "string",
         "value": "={{ $env.LUCRORADAR_API_URL || 'http://localhost:8000' }}"},
        {"id": "c2", "name": "start", "type": "string", "value": ""},
        {"id": "c3", "name": "end", "type": "string", "value": ""},
        {"id": "c4", "name": "margin_drop_pp", "type": "number", "value": 1.5},
        {"id": "c5", "name": "overdue_growth_pct", "type": "number", "value": 0.15},
        {"id": "c6", "name": "min_high_alerts", "type": "number", "value": 1},
    ]}, "options": {}}, "id": "a2", "name": "Configuração", "type": "n8n-nodes-base.set",
     "typeVersion": 3.4, "position": [220, 300]},
    {"parameters": {
        "url": "={{ $json.api_url }}/api/v1/automation/summary"
               "{{ $json.start && $json.end ? '?start=' + $json.start + '&end=' + $json.end : '' }}",
        "options": {"timeout": 30000}},
     "id": "a3", "name": "Consultar resumo (API)", "type": "n8n-nodes-base.httpRequest",
     "typeVersion": 4.2, "position": [440, 300]},
    {"parameters": {"jsCode": code_node}, "id": "a4", "name": "Verificar condições",
     "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 300]},
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                                   "conditions": [{"id": "i1", "leftValue": "={{ $json.should_alert }}",
                                                   "rightValue": True,
                                                   "operator": {"type": "boolean", "operation": "true",
                                                                "singleValue": True}}],
                                   "combinator": "and"}, "options": {}},
     "id": "a5", "name": "Há condição de alerta?", "type": "n8n-nodes-base.if", "typeVersion": 2,
     "position": [880, 300]},
    {"parameters": {}, "id": "a6", "name": "Alerta preparado (saída de teste)", "type": "n8n-nodes-base.noOp",
     "typeVersion": 1, "position": [1100, 200]},
    {"parameters": {}, "id": "a7", "name": "Resumo preparado (saída de teste)", "type": "n8n-nodes-base.noOp",
     "typeVersion": 1, "position": [1100, 420]},
    {"parameters": {"fromEmail": "alertas@exemplo.invalid", "toEmail": "gestor@exemplo.invalid",
                    "subject": "={{ $json.subject }}", "emailFormat": "text", "text": "={{ $json.body }}",
                    "options": {}},
     "id": "a8", "name": "Enviar e-mail (DESATIVADO — requer SMTP)", "type": "n8n-nodes-base.emailSend",
     "typeVersion": 2.1, "position": [1320, 200], "disabled": True,
     "notes": "Exemplo. Exige credencial SMTP configurada no n8n. Mantido desativado por padrão."},
]
connections = {
    "Executar manualmente": {"main": [[{"node": "Configuração", "type": "main", "index": 0}]]},
    "Configuração": {"main": [[{"node": "Consultar resumo (API)", "type": "main", "index": 0}]]},
    "Consultar resumo (API)": {"main": [[{"node": "Verificar condições", "type": "main", "index": 0}]]},
    "Verificar condições": {"main": [[{"node": "Há condição de alerta?", "type": "main", "index": 0}]]},
    "Há condição de alerta?": {"main": [
        [{"node": "Alerta preparado (saída de teste)", "type": "main", "index": 0}],
        [{"node": "Resumo preparado (saída de teste)", "type": "main", "index": 0}]]},
    "Alerta preparado (saída de teste)": {"main": [[{"node": "Enviar e-mail (DESATIVADO — requer SMTP)",
                                                      "type": "main", "index": 0}]]},
}
wf = {"name": "LucroRadar — resumo executivo e alertas", "nodes": nodes, "connections": connections,
      "settings": {"executionOrder": "v1"}, "pinData": {}, "active": False,
      "meta": {"templateCredsSetupCompleted": False}, "tags": []}
(HERE / "lucroradar-resumo-executivo.json").write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8")
print("ok")
