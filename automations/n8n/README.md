# Automação n8n — resumo executivo e alertas

Workflow importável: `lucroradar-resumo-executivo.json` (gerado por `build_workflow.py` a partir
de `check_conditions.js`, que tem teste próprio).

```
Executar manualmente → Configuração → Consultar resumo (API) → Verificar condições
    → Há condição de alerta? → sim: Alerta preparado (saída de teste) → [E-mail DESATIVADO]
                             → não: Resumo preparado (saída de teste)
```

## Como usar

1. Suba a API (`make api` ou `docker compose up`).
2. Suba o n8n: `docker compose --profile automation up n8n` (ou uma instalação própria).
3. No n8n: *Workflows → Import from File* → `lucroradar-resumo-executivo.json`.
4. Ajuste o nó **Configuração**: `api_url` (no Compose já vem de `LUCRORADAR_API_URL=http://api:8000`),
   período (`start`/`end` no formato AAAA-MM; vazio = últimos 3 meses) e limiares
   (`margin_drop_pp`, `overdue_growth_pct`, `min_high_alerts`).
5. Clique em **Execute workflow**. O resultado aparece no nó de saída de teste — nada é enviado.

## Payloads de exemplo

- `examples/summary-response.json` — resposta real de `GET /api/v1/automation/summary?start=2026-01&end=2026-06`.
- `examples/verificar-condicoes-output.json` — saída do nó "Verificar condições" para esse payload.

## Integrações que exigem configuração externa

| Integração | Situação |
|---|---|
| E-mail (nó "Enviar e-mail") | **Desativado.** Requer credencial SMTP no n8n e endereços reais. |
| Slack/Teams/WhatsApp | Não incluído. Substitua o nó de e-mail pelo nó correspondente e configure a credencial. |
| Agendamento | Não incluído. Troque o gatilho manual por *Schedule Trigger* quando desejar. |

## Teste

```bash
node automations/n8n/test_check_conditions.mjs
python3 automations/n8n/build_workflow.py   # regenera o JSON após mudar a lógica
```

Verificado com n8n 1.110.1 via CLI (`n8n import:workflow` + `n8n execute`) contra a API do
Docker Compose: todos os nós executaram, o ramo de alerta foi seguido e nada foi enviado. No n8n,
nós desativados apenas repassam os dados — o nó de e-mail não envia enquanto estiver desativado.
