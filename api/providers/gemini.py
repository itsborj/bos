from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiAdapter(OpenAICompatAdapter):
    provider_id = "gemini"

    def __init__(self, api_key: str) -> None:
        super().__init__("gemini", _BASE_URL, api_key)
