"""OpenRouter chat provider and free-model catalogue helpers."""
import json
from urllib.request import Request, urlopen

from .openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    def __init__(self, api_key, base_url="https://openrouter.ai/api/v1"):
        super().__init__(api_key, base_url)

    def estimate_cost(self, input_tokens, output_tokens):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": 0.0}


def _json_get(url, api_key="", timeout=30):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:
        return json.load(response)


def free_text_models(api_key=""):
    """Return OpenRouter models that are free and accept/produce text."""
    rows = _json_get("https://openrouter.ai/api/v1/models", api_key).get("data", [])
    result = []
    for row in rows:
        architecture = row.get("architecture") or {}
        inputs = architecture.get("input_modalities", architecture.get("modality", "text"))
        outputs = architecture.get("output_modalities", "text")
        if row.get("id", "").endswith(":free") and "text" in inputs and "text" in outputs:
            result.append(row)
    return result


def key_info(api_key):
    return _json_get("https://openrouter.ai/api/v1/key", api_key).get("data", {})


def is_free_tier(api_key):
    info = key_info(api_key)
    return bool(info.get("is_free_tier", info.get("limit") == 0))
