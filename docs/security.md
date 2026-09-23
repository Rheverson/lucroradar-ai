# Segurança da demonstração pública

A topologia publicada (Vercel + Neon) e suas proteções específicas estão em
[`hosting.md`](hosting.md#segurança-nesta-topologia): token entre web e API, IP do visitante vindo
da borda, TLS e papel somente leitura no banco.

## Credenciais somente no servidor

- `ANTHROPIC_API_KEY` e `POSTGRES_*` são lidas apenas pelo processo da API (`pydantic-settings`,
  `SecretStr`). O Next.js não usa nenhuma variável `NEXT_PUBLIC_*`; o navegador só fala com
  `/api/*` do próprio web, que repassa ao endereço interno `API_URL`.
- `/api/v1/meta`, `/api/v1/copilot/status` e `/api/health` não retornam segredos (teste
  `test_meta_and_status_do_not_expose_credentials`).
- `APP_ENV=production` recusa iniciar com a senha padrão de desenvolvimento do banco.
- `.env` está no `.gitignore`; `.env.example` só tem valores de exemplo.

## Endpoints públicos somente de leitura

- A sessão da API com o banco é `default_transaction_read_only=on` e `statement_timeout=15s`.
- Os `POST` (`simulator/run`, `proposal`, `copilot/ask`) só calculam; nada é gravado.
- SQL fixo e parametrizado; filtros validados contra lista fechada; `source-record` aceita só
  tabelas de uma lista branca.
- Proxy do web: apenas rotas `health` e `v1/...`, corpo máximo de 8 KB, timeout de 30 s (120 s
  para o copiloto).
- Recomendado em produção: usuário de banco com `GRANT SELECT` apenas (ver `docs/hosting.md`).

## Erros sem detalhes internos

- Exceções inesperadas retornam `{"detail": "Erro interno…", "error_id": …}`; o detalhe fica só no
  log (teste `test_unexpected_errors_hide_internal_details`).
- `/api/health` não mostra mais a mensagem do driver do banco.
- Erros do provedor de IA viram mensagens genéricas por categoria (teste offline com o SDK).
- `APP_ENV=production` desliga `/docs` e `/openapi.json`.
- Web envia `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options`,
  `Referrer-Policy` e `Permissions-Policy`.

## Limites de uso do copiloto

| Limite | Valor padrão | Onde |
|---|---|---|
| Tamanho da pergunta | 600 caracteres | API (validação) e interface |
| Perguntas livres por IP | 6 por minuto | `COPILOT_REQUESTS_PER_MINUTE` |
| Perguntas livres por dia (global) | 200 | `COPILOT_DAILY_LIMIT` |
| Chamadas de ferramenta por pergunta | 6 | `COPILOT_MAX_TOOL_CALLS` |
| Tokens de saída por chamada | 1500 | `COPILOT_MAX_OUTPUT_TOKENS` |
| Timeout por chamada / laço | 45 s / 90 s | `COPILOT_TIMEOUT_SECONDS` |

Perguntas demonstrativas não chamam o modelo e não contam nos limites. O IP do visitante é
repassado pelo proxy do web: em `X-LR-Client-IP` junto com o token (`PROXY_SHARED_SECRET`,
hospedagem) ou em `X-Forwarded-For` quando `TRUST_FORWARDED_FOR=true` (Compose, com a porta da
API restrita a `127.0.0.1`). Em qualquer outro caso, cabeçalhos do cliente são ignorados.

## Pendências

- Limites ficam na memória de cada instância: antes de ligar um provedor pago, usar um
  limitador compartilhado.
- Limite de taxa geral por IP depende da proteção da borda da hospedagem (planos gratuitos).
- Orçamento e alertas de custo no console do provedor de IA, se o modo generativo for ligado.
- Avaliação com o provedor real ainda **não executada** (modo generativo desligado na demo).
