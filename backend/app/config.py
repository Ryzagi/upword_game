from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    corpus_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    log_level: str = "INFO"
    # Optional MyMemory email — lifts free daily quota from 1k → 10k chars.
    translation_email: str = ""
    # Set true in test environments to use the NoopTranslator stub.
    translator_disabled: bool = False

    # OpenAI — used by the in-lobby AI theme generator.
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-2026-03-05"
    # "low" | "medium" | "high" — passed through as `reasoning_effort` on
    # models that support it; ignored on models that don't.
    openai_reasoning_effort: str = "medium"
    # Translator model — small/fast model is best for short translations.
    openai_translation_model: str = "gpt-5.4-nano-2026-03-17"


@lru_cache
def get_settings() -> Settings:
    return Settings()
