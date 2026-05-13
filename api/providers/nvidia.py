from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaAdapter(OpenAICompatAdapter):
    provider_id = "nvidia"

    def __init__(self, api_key: str) -> None:
        super().__init__("nvidia", _BASE_URL, api_key)
