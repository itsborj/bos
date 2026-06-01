import base64
import logging
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_SECRETS_DIR = Path(os.environ.get("BOS_SECRETS_DIR", "/data/secrets"))
_DEFAULT_KEY = "dev-key-change-me"


def _load(filename: str) -> str | None:
    path = _SECRETS_DIR / filename
    if path.exists():
        val = path.read_text().strip()
        return val or None
    return None


def _persist(filename: str, value: str) -> None:
    try:
        _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        (_SECRETS_DIR / filename).write_text(value)
    except OSError as exc:
        logger.warning(
            "Could not persist %s to secrets volume: %s — key will regenerate on restart",
            filename,
            exc,
        )


def _workspace_name_from_url(url: str) -> str:
    host = urlparse(url).hostname or "My Workspace"
    return host[4:] if host.startswith("www.") else host


async def ensure_workspace(frontend_url: str) -> None:
    """Bootstrap a default workspace row at first boot if the table is empty."""
    from sqlalchemy import func, select

    from db import get_session_factory
    from models.workspace import Workspace

    try:
        async with get_session_factory()() as db:
            count = await db.scalar(select(func.count()).select_from(Workspace))
            if count == 0:
                name = _workspace_name_from_url(frontend_url)
                db.add(Workspace(name=name))
                await db.commit()
                logger.info("first_boot: created default workspace '%s'", name)
    except Exception as exc:
        logger.warning("first_boot: could not bootstrap workspace: %s", exc)


def ensure_secrets() -> None:
    """Auto-generate API_SECRET_KEY and ENCRYPTION_KEY at first boot if absent.

    Must be called before get_settings() so pydantic picks up the generated values.
    Persists generated keys to BOS_SECRETS_DIR (/data/secrets by default) so they
    survive container restarts without ever being written to an env file.
    """
    # API_SECRET_KEY
    current = os.environ.get("API_SECRET_KEY", _DEFAULT_KEY)
    if not current or current == _DEFAULT_KEY:
        persisted = _load("api_secret_key")
        if persisted:
            os.environ["API_SECRET_KEY"] = persisted
            logger.info("first_boot: API_SECRET_KEY loaded from secrets volume")
        else:
            key = secrets.token_hex(32)
            _persist("api_secret_key", key)
            os.environ["API_SECRET_KEY"] = key
            logger.info("first_boot: API_SECRET_KEY auto-generated and persisted to secrets volume")

    # ENCRYPTION_KEY
    if not os.environ.get("ENCRYPTION_KEY", ""):
        persisted = _load("encryption_key")
        if persisted:
            os.environ["ENCRYPTION_KEY"] = persisted
            logger.info("first_boot: ENCRYPTION_KEY loaded from secrets volume")
        else:
            enc_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            _persist("encryption_key", enc_key)
            os.environ["ENCRYPTION_KEY"] = enc_key
            logger.info("first_boot: ENCRYPTION_KEY auto-generated and persisted to secrets volume")
