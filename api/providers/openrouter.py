import httpx

from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(OpenAICompatAdapter):
    provider_id = "openrouter"

    def __init__(self, api_key: str) -> None:
        super().__init__("openrouter", _BASE_URL, api_key)

    async def check(self) -> bool:
        """OpenRouter's /models is public — use /auth/key which requires a valid key."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/auth/key", headers=headers)
        return resp.status_code == 200
