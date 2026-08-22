from .openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        super().__init__(api_key, base_url)
