from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://bos:bos@db:5432/bos"
    api_secret_key: str = "dev-key-change-me"
    platform_openrouter_key: str = ""
    platform_gemini_key: str = ""
    platform_nvidia_key: str = ""
    platform_openai_key: str = ""
    encryption_key: str = ""
    markup_multiplier: float = 1.35

    # Optional fixed CMO model routing. Use provider:model_id, e.g.
    # openrouter:openai/gpt-4o-mini or gemini:gemini-2.0-flash.
    cmo_chat_model: str = ""
    # Modality-aware target backend overrides keyed by cmo/module/evaluator target.
    # Example: {"cmo.main":{"provider":"openai","model_id":"gpt-5.1","modality":"text"}}
    execution_backend_overrides: str = ""
    # Backward-compatible text-only module overrides: {"module.id":"provider:model_id"}.
    module_model_overrides: str = ""
    # True = configured module backend must be used; False = try it first, then fall back.
    strict_model_overrides: bool = True

    # Google / Gmail OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/social/gmail/callback"
    google_calendar_redirect_uri: str = ""

    # Frontend base URL — used to redirect after OAuth callbacks
    frontend_url: str = "http://localhost"

    app_version: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
