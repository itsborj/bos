import base64
import logging
from functools import lru_cache

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "postgresql://bos:bos@db:5432/bos"
    api_secret_key: str = "dev-key-change-me"
    platform_openrouter_key: str = ""
    platform_gemini_key: str = ""
    platform_nvidia_key: str = ""
    platform_openai_key: str = ""
    platform_bytedance_key: str = ""
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
    # Browser API key for the Google Picker (folder selection). Separate from the OAuth client.
    google_picker_api_key: str = ""
    
    # Whitelist of emails allowed to log in via Google Auth (comma-separated)
    admin_emails: str = ""

    # Google Ads API
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    google_ads_login_customer_id: str = ""
    google_ads_default_customer_id: str = ""

    # Google Analytics
    google_analytics_client_id: str = ""
    google_analytics_client_secret: str = ""
    google_analytics_refresh_token: str = ""
    google_analytics_property_id: str = ""

    # Meta (Facebook / Instagram) OAuth
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost/social/facebook/callback"

    # TikTok OAuth
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost/social/tiktok/callback"
    tiktok_scopes: str = "user.info.basic"

    # Auth relay — empty = dev mode (direct OAuth with local GOOGLE_CLIENT_ID/SECRET)
    klaroha_relay_url: str = ""
    klaroha_relay_key: str = ""

    # Frontend base URL — used to redirect after OAuth callbacks
    frontend_url: str = "http://localhost"

    app_version: str = "0.1.0"
    git_sha: str = "dev"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def validate_settings(s: "Settings") -> None:
    """Validate critical settings at startup. Raises RuntimeError on fatal misconfiguration."""
    errors: list[str] = []

    if s.encryption_key:
        try:
            padding = (4 - len(s.encryption_key) % 4) % 4
            decoded = base64.urlsafe_b64decode(s.encryption_key + "=" * padding)
            if len(decoded) != 32:
                errors.append(
                    f"ENCRYPTION_KEY decodes to {len(decoded)} bytes, expected 32. "
                    "Regenerate: python3 -c \"import base64,secrets; "
                    "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
                )
        except Exception:
            errors.append(
                "ENCRYPTION_KEY is not valid base64url. "
                "Regenerate: python3 -c \"import base64,secrets; "
                "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
            )
    else:
        logger.warning("ENCRYPTION_KEY not set — BYOK key storage will not work")

    if s.api_secret_key == "dev-key-change-me":
        logger.warning("API_SECRET_KEY is the insecure default — auto-generation via first_boot requires a writable /data/secrets volume")

    has_llm = any([s.platform_openrouter_key, s.platform_gemini_key, s.platform_nvidia_key, s.platform_openai_key])
    if not has_llm:
        logger.warning("No LLM provider key set — CMO will not function until at least one provider key is configured")

    if errors:
        for e in errors:
            logger.error("STARTUP ERROR: %s", e)
        raise RuntimeError(f"BOS startup validation failed ({len(errors)} error(s)). Check logs above.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
