from .base import Provider, ProviderResponse


class GeminiProvider(Provider):
    def __init__(self, api_key, base_url=None):
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def _prompt(self, messages): return "\n\n".join(f'{m["role"]}: {m["content"]}' for m in messages)
    def call(self, messages, model, temperature, max_tokens):
        from google.genai import types
        r = self.client.models.generate_content(model=model, contents=self._prompt(messages), config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens))
        usage = r.usage_metadata
        return ProviderResponse(r.text or "", usage.prompt_token_count or 0, usage.candidates_token_count or 0)
    def stream(self, messages, model, temperature, max_tokens):
        for chunk in self.client.models.generate_content_stream(model=model, contents=self._prompt(messages)):
            if chunk.text: yield chunk.text
    def estimate_cost(self, input_tokens, output_tokens):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": 0.0}
