from pathlib import Path
from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    # API Keys
    groq_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")

    # LLM Provider Configuration — dynamically configurable via JNAARA_* env vars
    primary_llm: Literal["groq", "gemini", "mock"] = "groq"
    primary_model: str = "openai/gpt-oss-120b"
    secondary_llm: Literal["groq", "gemini", "mock"] = "gemini"
    secondary_model: str = "gemini-2.5-flash"

    # Application Persistence & Strategy
    db_path: Path = Path("data/jnaara.db")
    default_strategy: Literal["recency", "corroboration"] = "recency"

    model_config = SettingsConfigDict(
        env_prefix="JNAARA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton instance helper
def get_settings() -> Settings:
    return Settings()
