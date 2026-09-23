# Copiloto de IA

## Modos

| Modo | Quando | Como responde |
|---|---|---|
| **Demonstração sem modelo generativo** | `ANTHROPIC_API_KEY` vazia (padrão) | Roteiros por pergunta que chamam as mesmas ferramentas e redigem por regras. Não simula chamada a LLM |
| Modelo generativo (servidor) | `ANTHROPIC_API_KEY` definida na API | Laço de tool use com Claude; resposta final via ferramenta `submit_answer` |

Perguntas demonstrativas continuam determinísticas mesmo com chave.

## Ferramentas controladas

`get_kpi_summary`, `get_margin_variation`, `get_contribution_ranking`, `get_overdue_receivables`,
`get_fleet_utilization`, `get_stage_times`, `get_data_quality_issues`.

- Sem SQL arbitrário: cada ferramenta chama uma função de `metrics.py`.
- Parâmetros validados com a mesma função dos filtros da tela; parâmetros desconhecidos são
  rejeitados; no máximo 10 linhas por ranking.
- **Filtros da tela prevalecem:** se o modelo pedir outro segmento/região/negócio/linha, o filtro
  da tela é mantido e um aviso aparece na resposta.
- Cada ferramenta devolve evidências numeradas (`E1`, `E2`…). O modelo só cita IDs; números vêm
  das evidências. Números no resumo que não existem nas evidências são listados em
  `unsupported_numbers` e sinalizados na interface.

## Resposta

Resumo · período e filtros · evidências (rótulo e valor formatado) · limitações · nota de
associação ≠ causa · links para a análise correspondente · ferramentas chamadas · avisos.

## Configuração (modo LLM)

| Variável | Padrão | Uso |
|---|---|---|
| `ANTHROPIC_API_KEY` | vazio | Chave, somente no processo da API |
| `COPILOT_MODEL` | `claude-opus-5` | Modelo |
| `COPILOT_EFFORT` | `medium` | Esforço de raciocínio |
| `COPILOT_TIMEOUT_SECONDS` | 45 | Timeout por chamada (o laço inteiro tem limite de 2×) |
| `COPILOT_MAX_TOOL_CALLS` | 6 | Chamadas de ferramenta por pergunta |
| `COPILOT_MAX_OUTPUT_TOKENS` | 1500 | Tokens de saída por chamada |
| `COPILOT_REQUESTS_PER_MINUTE` | 6 | Limite por IP (só perguntas livres no modo LLM) |
| `COPILOT_DAILY_LIMIT` | 200 | Teto global diário de perguntas livres ao modelo (controle de custo) |

A requisição usa o SDK oficial `anthropic` (`client.beta.messages.create`) com o beta de
fallback do servidor (`fallbacks: "default"`) para recusas. Tratamento: chave inválida, limite
de taxa, timeout, erro de conexão, recusa (`stop_reason = refusal`) e `max_tokens` viram
mensagens claras (HTTP 4xx/5xx), sem expor detalhes internos. Pergunta limitada a 600
caracteres. A chave nunca é enviada ao navegador; o Next.js só repassa `/api/*`.

**Limitações de uso:** cada pergunta livre consome tokens do provedor (custo); respostas podem
variar entre execuções; o modelo pode escolher ferramentas menos adequadas — as evidências
sempre permitem conferir. A integração com chave real **não foi executada** neste ambiente
(sem credencial); a mecânica do laço foi testada com cliente falso.

## Avaliar o provedor real (sem colar a chave em lugar nenhum público)

A chave **nunca** deve ser colada em chat, issue, commit ou variável `NEXT_PUBLIC_*`. Configure-a
como segredo em um destes lugares, conforme onde a avaliação vai rodar:

| Onde roda | Onde configurar | Nome |
|---|---|---|
| Sua máquina | arquivo `.env` na raiz (já ignorado pelo git) ou variável exportada no terminal | `ANTHROPIC_API_KEY` |
| Sessão do Claude Code na nuvem | menu do ambiente no título da sessão → **Edit** → variáveis de ambiente/credenciais; vale para uma **nova** sessão | `ANTHROPIC_API_KEY` |
| GitHub Actions | *Settings → Environments → `llm-eval` → Environment secrets* (ou *Settings → Secrets and variables → Actions*) | `ANTHROPIC_API_KEY` |
| Hospedagem futura | cofre de segredos do provedor, atribuído só ao serviço da API | `ANTHROPIC_API_KEY` |

Execução:

```bash
make eval-llm                  # local; grava reports/llm-eval.json
```

ou, no GitHub, **Actions → "Avaliação do copiloto (LLM real)" → Run workflow** (manual; consome
tokens pagos). O relatório tem `status`: `nao_executado`, `aprovado` ou `reprovado`.
**Enquanto o status não for `aprovado` a partir de uma execução real, o modo LLM não está
avaliado.** Sem chave, o script grava `nao_executado` e sai com código 2.

Verificações que **já rodam sem chave** (`tests/python/test_copilot_sdk_offline.py`): o SDK
oficial monta a requisição correta (modelo, ferramentas, beta de fallback) e converte erros
401/429/500 em mensagens genéricas — usando transporte HTTP simulado, sem rede.

## Avaliações

- `tests/python/test_copilot_evals.py` (roda sem chave): perguntas com resultado conhecido pelo
  manifesto (vendedores do desconto, clientes atrasados, SKU ocioso, gargalo), fidelidade
  numérica contra o serviço de métricas, respeito a filtros, ausência de números sem evidência,
  pergunta fora de escopo sem resposta inventada; laço LLM com cliente falso (filtro travado,
  evidência inexistente, número inventado, ferramenta desconhecida, recusa).
- `tests/evals/run_llm_evals.py` (com chave): mesmas verificações contra o modelo real.
