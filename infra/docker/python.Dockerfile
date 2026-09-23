# Imagem Python única para o pipeline (gerador + ingestão + dbt) e para a API.
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.8.17
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --all-extras --no-install-project
COPY data/generator data/generator
COPY data/ingestion data/ingestion
COPY services/api services/api
COPY analytics/dbt analytics/dbt
RUN uv sync --frozen --no-dev --all-extras
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home app && mkdir -p data/landing data/manifest analytics/dbt/target analytics/dbt/logs \
    && chown -R app /app/data /app/analytics/dbt
USER app
EXPOSE 8000
CMD ["uvicorn", "lucroradar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
