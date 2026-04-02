"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──
    app_name: str = "Scoping Review AI"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # ── Database ──
    postgres_user: str = "scopingreview"
    postgres_password: str = "scopingreview_secret_2024"
    postgres_db: str = "scoping_review_db"
    postgres_host: str = "db"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Redis ──
    redis_url: str = "redis://redis:6379/0"

    # ── JWT Auth ──
    secret_key: str = "change-me-to-a-random-64-char-string-in-production"
    access_token_expire_minutes: int = 1440
    default_admin_email: str = "admin@scopingreview.local"
    default_admin_password: str = "changeme123"

    # ── LLM Providers ──
    ollama_base_url: str = "http://ollama:11434"
    gemini_api_key: str = ""
    groq_api_key: str = ""

    primary_llm_provider: Literal["ollama", "gemini", "groq"] = "gemini"
    primary_llm_model: str = "gemini-2.0-flash"
    validator_llm_provider: Literal["ollama", "gemini", "groq"] = "groq"
    validator_llm_model: str = "llama-3.3-70b-versatile"

    # ── Embeddings ──
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    # ── PubMed ──
    pubmed_email: str = "your-email@example.com"
    pubmed_rate_limit: int = 3

    # ── Uploads ──
    upload_dir: str = "/app/uploads"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
