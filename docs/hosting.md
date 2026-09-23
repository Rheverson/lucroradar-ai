# Hospedagem futura (não realizada)

Nada foi publicado. Roteiro sugerido:

1. **Banco:** PostgreSQL 16 gerenciado (ex.: serviço gerenciado de nuvem). Criar usuário
   somente leitura para a API (`GRANT SELECT` em `staging`, `marts`, `quality`, `audit`,
   `reference`) e outro com escrita para o pipeline.
2. **Pipeline:** executar a imagem `infra/docker/python.Dockerfile` como job agendado ou manual
   (`lucroradar-ingest run --generate`). Os dados são sintéticos; regenerar é seguro.
3. **API:** mesma imagem, comando padrão (`uvicorn`). Variáveis: `POSTGRES_*` (usuário somente
   leitura), `CORS_ORIGINS`, `REPOSITORY_URL`, opcionalmente `ANTHROPIC_API_KEY` como segredo do
   provedor de hospedagem. Atrás de HTTPS.
4. **Web:** `apps/web/Dockerfile` (saída `standalone`) com `API_URL` apontando para a API interna.
5. **Proteções para demonstração pública:** limite de taxa no proxy/API; orçamento/alertas de
   custo no provedor de LLM; manter o modo demonstração como padrão.
6. **n8n:** instância própria, sem credenciais de envio até decisão explícita.
7. Gerar `test-summary.json` no CI e copiá-lo para `apps/web/public` antes do build da web.
