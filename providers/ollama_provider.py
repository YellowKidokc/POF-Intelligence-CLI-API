import requests
from .base import Provider, ProviderResponse


class OllamaProvider(Provider):
    def __init__(self, base_url="http://localhost:11434", api_key=""):
        self.base_url = base_url.rstrip("/")

    def call(self, messages, model, temperature, max_tokens):
        response = requests.post(f"{self.base_url}/api/chat", json={"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature, "num_predict": max_tokens}}, timeout=300)
        response.raise_for_status(); data = response.json()
        return ProviderResponse(data["message"]["content"], data.get("prompt_eval_count", 0), data.get("eval_count", 0))

    def stream(self, messages, model, temperature, max_tokens):
        response = requests.post(f"{self.base_url}/api/chat", json={"model": model, "messages": messages, "stream": True}, stream=True, timeout=300)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                yield __import__("json").loads(line)["message"]["content"]

    def estimate_cost(self, input_tokens, output_tokens):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": 0.0}

    def embed(self, texts, model):
        vectors = []
        for text in texts:
            response = requests.post(f"{self.base_url}/api/embeddings", json={"model": model, "prompt": text}, timeout=300)
            response.raise_for_status(); vectors.append(response.json()["embedding"])
        return vectors
