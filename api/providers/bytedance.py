import asyncio
import time

import httpx

from providers.base import ProviderResponse
from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
_POLL_INTERVAL = 3.0
_POLL_TIMEOUT = 180.0


class ByteDanceAdapter(OpenAICompatAdapter):
    """BytePlus ModelArk adapter — supports text completions and async video generation."""

    provider_id = "bytedance"

    def __init__(self, api_key: str) -> None:
        super().__init__("bytedance", _BASE_URL, api_key)

    async def check(self) -> bool:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE_URL}/models", headers=headers)
        return resp.status_code == 200

    async def generate_video(
        self,
        prompt: str,
        model_id: str,
        *,
        resolution: str = "480p",
        ratio: str = "16:9",
        duration: int = 4,
        generate_audio: bool = False,
        watermark: bool = True,
    ) -> ProviderResponse:
        """Submit a video generation task and poll until complete. Returns video URL as content."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "content": [{"type": "text", "text": prompt}],
            "resolution": resolution,
            "ratio": ratio,
            "duration": duration,
            "generate_audio": generate_audio,
            "watermark": watermark,
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_BASE_URL}/contents/generations/tasks",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            task_id = resp.json()["id"]

            deadline = time.time() + _POLL_TIMEOUT
            while time.time() < deadline:
                await asyncio.sleep(_POLL_INTERVAL)
                poll = await client.get(
                    f"{_BASE_URL}/contents/generations/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=15.0,
                )
                poll.raise_for_status()
                data = poll.json()
                status = data.get("status")
                if status == "succeeded":
                    video_url = data["content"]["video_url"]
                    usage = data.get("usage", {})
                    latency_ms = round((time.perf_counter() - start) * 1000)
                    return ProviderResponse(
                        content=video_url,
                        tokens_input=usage.get("total_tokens", 0),
                        tokens_output=0,
                        latency_ms=latency_ms,
                    )
                if status in ("failed", "cancelled"):
                    raise RuntimeError(
                        f"ByteDance video generation {status}: {data.get('error', {})}"
                    )
        raise TimeoutError(
            f"ByteDance video generation timed out after {_POLL_TIMEOUT}s (task {task_id})"
        )
