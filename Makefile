# Atalhos. Requer uv, Node 22 e PostgreSQL 16 (ou use `make up` com Docker).
# .PHONY inclui eval-llm
.PHONY: eval-llm install pipeline api web dev test test-python test-dbt test-e2e test-n8n lint summary up down clean

install:
	uv sync --all-extras
	cd apps/web && npm ci

pipeline:            ## gera dados sintéticos, carrega (idempotente) e roda dbt build
	uv run lucroradar-ingest run --generate

api:
	uv run uvicorn lucroradar_api.main:app --port 8000

web:
	cd apps/web && npm run dev

test: test-python test-n8n test-dbt summary

test-python:
	mkdir -p reports && uv run pytest --junitxml=reports/pytest.xml

test-dbt:
	cd analytics/dbt && uv run dbt build

test-n8n:
	./scripts/run_n8n_logic_test.sh

test-e2e:            ## requer API e web em execução
	cd apps/web && npx playwright test

lint:
	uv run ruff check .
	cd apps/web && npx eslint . && npx tsc --noEmit

summary:
	uv run python scripts/collect_test_summary.py

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf data/landing data/manifest analytics/dbt/target reports

eval-llm:            ## avaliação com o provedor real; lê ANTHROPIC_API_KEY do ambiente ou do .env (nunca do chat)
	uv run python tests/evals/run_llm_evals.py
