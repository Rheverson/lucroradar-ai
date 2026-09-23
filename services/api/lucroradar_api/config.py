"""Configuração do servidor via variáveis de ambiente (nunca enviadas ao navegador)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "lucroradar"
    postgres_password: SecretStr = SecretStr("lucroradar")
    postgres_db: str = "lucroradar"
    postgres_sslmode: str | None = None  # require/verify-full em bancos gerenciados
    # Alternativa única: DATABASE_URL (ex.: string do Neon com sslmode=require). Tem precedência.
    database_url: SecretStr | None = None
    db_pool_max_size: int = 4

    # Copiloto: sem chave → modo "Demonstração sem modelo generativo"
    anthropic_api_key: SecretStr | None = None
    copilot_model: str = "claude-opus-5"
    copilot_effort: str = "medium"  # low | medium | high | xhigh | max
    copilot_requests_per_minute: int = 6  # por IP, só no modo LLM
    copilot_daily_limit: int = 200  # teto global de perguntas livres ao LLM por dia (controle de custo)

    # Exposição pública
    app_env: str = "development"  # development | production
    trust_forwarded_for: bool = False  # True só atrás de um proxy confiável (rede privada, ex.: Compose)
    # Topologia pública (web e API em domínios distintos): o proxy do web envia este segredo
    # em X-LR-Proxy-Token. Com ele definido, /api/v1/* exige o token e o IP do visitante
    # só é aceito do cabeçalho X-LR-Client-IP de requisições autenticadas.
    proxy_shared_secret: SecretStr | None = None
    expose_api_docs: bool = True  # /docs e /openapi.json; desligar em produção
    copilot_timeout_seconds: float = 45.0
    copilot_max_question_chars: int = 600
    copilot_max_tool_calls: int = 6
    copilot_max_output_tokens: int = 1500

    repository_url: str = Field(default="https://github.com/Rheverson/lucroradar-ai")
    cors_origins: str = "http://localhost:3000"

    @property
    def conninfo(self) -> str:
        from psycopg.conninfo import make_conninfo

        if self.database_url and self.database_url.get_secret_value().strip():
            return self.database_url.get_secret_value().strip()
        extra = {"sslmode": self.postgres_sslmode} if self.postgres_sslmode else {}
        return make_conninfo(
            host=self.postgres_host, port=self.postgres_port, user=self.postgres_user,
            password=self.postgres_password.get_secret_value(), dbname=self.postgres_db, **extra,
        )

    @property
    def proxy_token(self) -> str | None:
        v = self.proxy_shared_secret.get_secret_value().strip() if self.proxy_shared_secret else ""
        return v or None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_for_runtime(self) -> None:
        """Em produção, recusa iniciar com a senha padrão de desenvolvimento."""
        if not self.is_production:
            return
        if self.database_url and self.database_url.get_secret_value().strip():
            url = self.database_url.get_secret_value()
            if "sslmode=require" not in url and "sslmode=verify" not in url:
                raise RuntimeError("APP_ENV=production exige DATABASE_URL com sslmode=require (TLS).")
        elif self.postgres_password.get_secret_value() in ("lucroradar", "", "troque-esta-senha-local"):
            raise RuntimeError("APP_ENV=production exige POSTGRES_PASSWORD definida (não use o valor padrão).")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
