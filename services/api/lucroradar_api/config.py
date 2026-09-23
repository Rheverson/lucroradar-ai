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

    # Copiloto: sem chave → modo "Demonstração sem modelo generativo"
    anthropic_api_key: SecretStr | None = None
    copilot_model: str = "claude-opus-5"
    copilot_effort: str = "medium"  # low | medium | high | xhigh | max
    copilot_requests_per_minute: int = 6  # por IP, só no modo LLM
    copilot_timeout_seconds: float = 45.0
    copilot_max_question_chars: int = 600
    copilot_max_tool_calls: int = 6
    copilot_max_output_tokens: int = 1500

    repository_url: str = Field(default="https://github.com/SEU-USUARIO/lucroradar-ai")
    cors_origins: str = "http://localhost:3000"

    @property
    def conninfo(self) -> str:
        from psycopg.conninfo import make_conninfo

        return make_conninfo(
            host=self.postgres_host, port=self.postgres_port, user=self.postgres_user,
            password=self.postgres_password.get_secret_value(), dbname=self.postgres_db,
        )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
