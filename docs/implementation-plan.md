# LucroRadar AI — Plano de implementação

> Documento vivo. Atualizado ao fim de cada etapa com o que foi **verificado**,
> o que é **demonstração** e o que está **pendente**.

## Pergunta central

"Estou vendendo mais. Por que o dinheiro não está sobrando?"

Jornada: identificar queda de margem → investigar clientes/produtos/contratos →
perguntar ao copiloto → simular mudanças operacionais → gerar proposta de ação.

## Inspeção inicial (23/09/2026)

- O projeto foi desenvolvido inicialmente como subpasta de outro repositório e
  depois extraído para esta raiz própria, sem histórico nem arquivos daquele
  repositório (nada do outro projeto foi reaproveitado).
- O workflow de CI fica em `.github/workflows/ci.yml`.

## Decisões técnicas

| Tema | Escolha | Motivo |
|---|---|---|
| Python | 3.11+, `uv` com `uv.lock` | Reprodutível e rápido |
| Banco | PostgreSQL 16 | Pedido; `pg_trgm` para candidatos a duplicidade |
| Transformações | dbt Core + dbt-postgres, sem pacotes externos | Evita `dbt deps` com rede; testes genéricos próprios |
| API | FastAPI + psycopg 3, SQL parametrizado | Sem ORM: consultas analíticas explícitas |
| Web | Next.js (App Router) + TypeScript + Tailwind + Recharts | Pedido |
| IA | Interface `CopilotProvider`; `DemoProvider` e `AnthropicProvider` | Demonstração sem chave; integração real no servidor |
| Automação | n8n (JSON importável) | Pedido; execução manual por padrão |
| E2E | Playwright | Chromium já disponível no ambiente |

Simplificações documentadas:

- Modelos dbt materializados como `table`/`view` (reexecução idempotente por
  reconstrução). A incrementalidade fica na camada raw (lotes).
- Simulações são stateless: os parâmetros vivem no navegador
  (`sessionStorage`) e são enviados ao servidor, que só calcula. Nada é gravado
  em dados compartilhados.
- Sem autenticação: demonstração pública de leitura. Presets CEO/Financeiro/
  Operações são atalhos de filtros, não perfis de acesso.

## Etapas

1. **Fatia funcional** — gerador, PostgreSQL, ingestão, primeiro mart,
   endpoint real, tela executiva.
2. **Modelagem completa** — qualidade, quarentena, reconciliação,
   detalhamentos (clientes/produtos até a origem), candidatos a duplicidade.
3. **Simulador e operações** — funções determinísticas testadas, utilização,
   manutenção, tempo por etapa.
4. **Copiloto** — ferramentas controladas, modo demonstração, integração LLM,
   avaliações.
5. **Acabamento** — n8n, visual, documentação, capturas, CI.

## Status por etapa

Última verificação: 23/09/2026, neste ambiente (PostgreSQL 16 local + Docker Compose).

- [x] **Etapa 1 — fatia funcional.** Gerador determinístico (seed + data de referência, 18 meses,
  2 lotes, manifesto), PostgreSQL, ingestão idempotente, primeiro mart
  (`mart_contribution_monthly`), endpoint real e visão executiva consumindo a API.
- [x] **Etapa 2 — modelagem, qualidade e detalhamento.** Staging com quarentena, 57 modelos dbt,
  integridade referencial, reconciliação (9 verificações, todas "ok"), candidatos a duplicidade
  sem unificação automática, drill-down até a linha do arquivo raw.
- [x] **Etapa 3 — simulador, operações e locações.** Funções determinísticas testadas, teto
  físico de utilização, frota por unidade-dia, manutenção, tempo por etapa por eventos.
- [x] **Etapa 4 — copiloto.** Interface de provedor, 7 ferramentas controladas, modo
  "Demonstração sem modelo generativo", integração Anthropic no servidor com timeout, limites e
  tratamento de falhas, avaliações com resultado conhecido.
- [x] **Etapa 5 — automação, acabamento, documentação e CI.** Workflow n8n importável, interface
  responsiva clara/escura, documentação, capturas reais, licença, workflow do GitHub Actions.

### Verificado (resultados reais desta entrega)

| Verificação | Resultado |
|---|---|
| `pytest` (unitários, integração com banco, avaliações do copiloto) | 65/65 |
| `dbt build` | 119 nós, 58 testes de dados, 0 falhas |
| Playwright (jornada completa, filtros, drill-down, copiloto, simulador, teclado, celular) | 9/9 contra o servidor de desenvolvimento **e** contra o Docker Compose |
| Receita de venda por mês × manifesto do gerador | idêntica (centavos) |
| Vencido na referência × manifesto | idêntico |
| Reexecução do pipeline | 0 linhas novas; arquivos reconhecidos por hash |
| `docker compose up` do zero | db → pipeline → api → web saudáveis |
| Workflow n8n (n8n 1.110.1 via CLI) | importado e executado; ramo de alerta seguido; nada enviado |
| ruff, eslint, tsc, `next build` | sem erros |
| GitHub Actions (execução na versão ainda como subpasta) | 2/2 jobs com sucesso: web; pipeline + reexecução + pytest + n8n + Playwright. Nesta raiz independente o CI ainda não rodou (sem repositório remoto) |

Observação sobre o Docker neste ambiente: o registro Docker Hub limitou downloads (HTTP 429) e o
sandbox exige um proxy com CA próprio. A verificação usou imagens do espelho público
`mirror.gcr.io` e uma variante temporária dos Dockerfiles com o CA do proxy (fora do repositório).
Os Dockerfiles versionados não dependem disso.

### Validação da versão independente (23/09/2026)

Cópia extraída só com arquivos rastreados (sem histórico), validada em container recém-reiniciado,
banco vazio, `.venv` e `node_modules` novos.

| Verificação | Resultado | Tipo |
|---|---|---|
| `uv sync --frozen`, `npm ci`, ruff, eslint, tsc, `next build` | ok | concluída |
| Pipeline do zero + reexecução (0 linhas novas) | ok; dbt 119 nós, 58 testes | concluída |
| pytest (inclui segurança e SDK offline) | 72/72 | concluída |
| Playwright contra build de produção local | 9/9, sem violação de CSP | concluída |
| Lógica do workflow n8n | ok | concluída |
| Docker Compose do zero + Playwright 9/9 + n8n 1.110.1 | ok | **depende de adaptação local de proxy** (espelho `mirror.gcr.io` e CA do proxy injetada em cópia temporária dos Dockerfiles) |
| `APP_ENV=production`: recusa senha padrão; `/docs` desligado | ok (no container) | concluída |
| CI no GitHub desta raiz | não executado (sem repositório remoto) | bloqueada por decisão |
| Avaliação com provedor real de IA | não executada (sem chave) | bloqueada — requer segredo |

### Demonstração (funciona, mas com limites declarados)

- Copiloto sem chave: respostas roteirizadas por regras sobre os serviços de métricas.
- Proposta de ação: montada por regras a partir de alertas e simulação.

### Pendente / não verificado

- Chamada real ao modelo generativo (não há `ANTHROPIC_API_KEY` no ambiente). A mecânica do laço
  foi testada com cliente falso; `tests/evals/run_llm_evals.py` está pronto para rodar com chave.
- Hospedagem pública (fora do escopo; roteiro em `docs/hosting.md`).
- Envio real de e-mail/mensagens pelo n8n (desativado por decisão de projeto).
