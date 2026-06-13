from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from models.provider import ProviderKey
from provider_auth import encrypt_secret, resolve_stored_provider_credential


class _ExecuteResult:
    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _QueueDb:
    def __init__(self, rows):
        self._rows = list(rows)
        self.commits = 0

    async def execute(self, _statement):
        assert self._rows, "unexpected query"
        return _ExecuteResult(self._rows.pop(0))

    async def commit(self):
        self.commits += 1


def _settings():
    return SimpleNamespace(encryption_key=Fernet.generate_key().decode())


def _provider_key(workspace_id, provider: str, encrypted: str, *, brand_id=None, auth_mode="api_key") -> ProviderKey:
    return ProviderKey(
        workspace_id=workspace_id,
        brand_id=brand_id,
        provider=provider,
        auth_mode=auth_mode,
        key_encrypted=encrypted,
    )


@pytest.mark.asyncio
async def test_provider_credential_decryption_failure_raises_by_default() -> None:
    settings = _settings()
    workspace_id = uuid4()
    db = _QueueDb([
        _provider_key(workspace_id, "openai", "encrypted-with-an-old-key"),
    ])

    with pytest.raises(HTTPException) as exc:
        await resolve_stored_provider_credential(db, workspace_id, "openai", settings)

    assert exc.value.status_code == 500
    assert exc.value.detail["error"]["code"] == "DECRYPTION_FAILED"


@pytest.mark.asyncio
async def test_provider_credential_decryption_failure_can_fall_back_to_workspace_key() -> None:
    settings = _settings()
    workspace_id = uuid4()
    brand_id = uuid4()
    workspace_key = encrypt_secret("workspace-api-key", settings)
    db = _QueueDb([
        _provider_key(workspace_id, "openai", "encrypted-with-an-old-key", brand_id=brand_id),
        _provider_key(workspace_id, "openai", workspace_key),
    ])

    token, mode = await resolve_stored_provider_credential(
        db,
        workspace_id,
        "openai",
        settings,
        brand_id=brand_id,
        tolerate_decryption_failure=True,
    )

    assert token == "workspace-api-key"
    assert mode == "api_key"


@pytest.mark.asyncio
async def test_tolerated_provider_credential_decryption_failure_returns_missing_when_no_fallback() -> None:
    settings = _settings()
    workspace_id = uuid4()
    db = _QueueDb([
        _provider_key(workspace_id, "openai", "encrypted-with-an-old-key"),
    ])

    token, mode = await resolve_stored_provider_credential(
        db,
        workspace_id,
        "openai",
        settings,
        tolerate_decryption_failure=True,
    )

    assert token is None
    assert mode is None
