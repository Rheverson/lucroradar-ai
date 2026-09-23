# Hospedagem da demonstração pública (planos gratuitos)

Topologia publicada, sem nenhum serviço pago:

```
navegador ──HTTPS──▶ Vercel (Hobby) · projeto "web"  (Next.js, apps/web)
                          │  /api/*  proxy no servidor: rota permitida, corpo ≤ 8 KB,
                          │          timeout, X-LR-Proxy-Token + X-LR-Client-IP
                          ▼
                     Vercel (Hobby) · projeto "api"  (FastAPI como função Python)
                          │  DATABASE_URL do papel lucroradar_reader, sslmode=require,
                          │  sessão read-only, statement_timeout 15 s
                          ▼
                     Neon (Free) · PostgreSQL gerenciado
                          ▲
                          │  papel dono via integração Neon ↔ GitHub (ou LOADER_DATABASE_URL)
                     workflow manual "Carregar dados da demonstração"
```

| Peça | Serviço / plano | Observações |
|---|---|---|
| Código e CI | GitHub (repositório público) | Actions gratuito para repositórios públicos |
| Web | Vercel Hobby | Uso pessoal/não comercial; subdomínio `*.vercel.app` com HTTPS |
| API | Vercel Hobby (função Python via `[tool.vercel] entrypoint` no `pyproject.toml`) | Sem servidor sempre ligado; a primeira chamada após repouso é mais lenta |
| Banco | Neon Free | 0,5 GB por projeto, 100 CU-hora/mês, 5 GB de transferência/mês, suspende após 5 min sem uso |
| Carga de dados | GitHub Actions (manual) | A API **nunca** roda o pipeline ao iniciar |
| n8n | não hospedado | Workflow continua importável e testado no CI |
| Copiloto generativo | desligado | Sem `ANTHROPIC_API_KEY`; modo "Demonstração sem modelo generativo" |

Volume: o banco completo ocupa cerca de 90 MB (raw ≈ 19 MB, staging ≈ 23 MB, marts ≈ 35 MB),
bem abaixo do limite de 0,5 GB do Neon Free.

Os planos gratuitos não cobram excedente: ao atingir um limite, o serviço é suspenso até o
próximo ciclo (confirme no painel de cada serviço; não cadastre cartão para esta demonstração).
Não há pings artificiais para manter nada acordado: a interface mostra "Iniciando a
demonstração…" e repete as leituras automaticamente enquanto a API e o banco acordam.

## Passo a passo

### 1. Banco (Neon Free) — painel

1. Em <https://console.neon.tech>, crie um projeto (plano Free, região `AWS us-east-1`, a mesma
   das funções da Vercel por padrão), só com **Postgres database** ligado. Nome sugerido:
   `lucroradar-ai`.
2. **Integrations → GitHub → Add** e escolha o repositório `lucroradar-ai`. A integração grava
   no repositório o segredo `NEON_API_KEY` e a variável `NEON_PROJECT_ID`, usados apenas pelo
   workflow de carga. (Alternativa sem integração: segredo `LOADER_DATABASE_URL` com a string
   direta do papel dono e `sslmode=require`.)

### 2. Carga dos dados — GitHub

1. **Actions → Carregar dados da demonstração → Run workflow** (padrões: leitura
   `lucroradar_reader`, dono `neondb_owner`, banco `neondb`). O job:
   - cria o papel `lucroradar_reader` no Neon se ele não existir (a senha não é exibida);
   - obtém a string do papel dono na hora, com `sslmode=require`, mascarada nos logs;
   - gera os dados sintéticos (determinísticos), carrega só o que for novo e roda `dbt build`
     com os 58 testes;
   - concede `USAGE`/`SELECT` ao papel de leitura (com privilégios padrão para tabelas recriadas
     depois) e `default_transaction_read_only`.
2. Rodar de novo é seguro: os arquivos são reconhecidos pelo hash (0 linhas novas).
3. No painel do Neon, **Connect** → papel `lucroradar_reader`, "Connection pooling" desligado →
   copie a string (com `sslmode=require`) para a variável `DATABASE_URL` da API (passo 3).

### 3. API — projeto Vercel "api"

Diretório raiz `.`, framework FastAPI, entrada `vercel_app.py`. O `.vercelignore` da raiz vale
para os dois projetos e envia só o código necessário (sem dados gerados, testes ou
documentação). Variáveis (Production):

| Variável | Valor | Tipo |
|---|---|---|
| `DATABASE_URL` | string do `lucroradar_reader` com `sslmode=require` | Sensitive |
| `PROXY_SHARED_SECRET` | segredo aleatório (o mesmo do web) | Sensitive |
| `APP_ENV` | `production` (desliga `/docs`, exige TLS) | Plain |
| `CORS_ORIGINS` | vazio — o navegador nunca chama a API diretamente | Plain |
| `REPOSITORY_URL` | `https://github.com/Rheverson/lucroradar-ai` | Plain |

Depois de alterar variáveis, faça **Redeploy** do último deploy de produção.

### 4. Web — projeto Vercel "web"

Diretório raiz `apps/web`, framework Next.js. Variáveis (Production):

| Variável | Valor | Tipo |
|---|---|---|
| `API_URL` | URL de produção do projeto "api" | Plain |
| `PROXY_SHARED_SECRET` | o mesmo segredo da API | Sensitive |
| `SITE_URL` | URL pública do web | Plain |

## Segurança nesta topologia

- **A API é pública na internet** (funções da Vercel não ficam em rede privada). Por isso,
  com `PROXY_SHARED_SECRET` definido, `/api/v1/*` responde 403 sem o cabeçalho
  `X-LR-Proxy-Token` (comparação em tempo constante). O segredo só existe no servidor do web.
  `/api/health` continua aberto e não expõe dados nem detalhes do banco.
- **IP do visitante:** a borda da Vercel define `x-real-ip`/`x-forwarded-for` e sobrescreve o
  que o cliente enviar; o proxy repassa esse valor em `X-LR-Client-IP`, aceito pela API apenas em
  requisições autenticadas pelo token. Sem token e sem `TRUST_FORWARDED_FOR`, a API usa o IP da
  conexão e ignora cabeçalhos do cliente.
- **Limites do copiloto** ficam em memória por instância; como o modo generativo está desligado,
  não há custo em jogo. Antes de ligar um provedor pago, use um limitador compartilhado.
- **Banco:** TLS obrigatório (`validate_for_runtime` recusa iniciar em produção sem
  `sslmode=require`), papel somente leitura, sessão read-only e timeout de 15 s. A credencial de
  carga fica só no GitHub Actions.
- **Pool:** `min_size=0`, até 4 conexões, conexões ociosas fecham em 60 s, sem prepared
  statements — compatível com funções efêmeras e com o repouso do Neon.
- **Timeouts:** proxy 30 s (120 s para o copiloto); conexão ao banco 15 s; consulta 15 s.

## Alternativa: Render Free para a API

A imagem `infra/docker/python.Dockerfile` roda no Render (serviço web Free, porta `$PORT`,
health check `/api/health`). Lá a API também é pública: use `PROXY_SHARED_SECRET` da mesma forma.
O bind em `127.0.0.1` do Docker Compose **não** se aplica a esse ambiente.

## Execução local

Nada muda: `docker compose up --build` continua subindo banco, pipeline, API e web localmente.
