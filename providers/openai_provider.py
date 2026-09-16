from .base import Provider, ProviderResponse


PRICING = {
    "gpt-4o": (2.50, 10.00),
    "deepseek-chat": (0.27, 1.10),
    "text-embedding-3-small": (0.02, 0.0),
}


class OpenAIProvider(Provider):
    def __init__(self, api_key: str, base_url: str | None = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def call(self, messages, model, temperature, max_tokens):
        result = self.client.chat.completions.create(messages=messages, model=model, temperature=temperature, max_tokens=max_tokens)
        usage = result.usage
        return ProviderResponse(result.choices[0].message.content or "", usage.prompt_tokens, usage.completion_tokens)

    def stream(self, messages, model, temperature, max_tokens):
        for event in self.client.chat.completions.create(messages=messages, model=model, temperature=temperature, max_tokens=max_tokens, stream=True):
            text = event.choices[0].delta.content
            if text:
                yield text

    def estimate_cost(self, input_tokens, output_tokens):
        rates = PRICING.get(getattr(self, "model", ""), (0.0, 0.0))
        cost = (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}

    def embed(self, texts, model="text-embedding-3-small"):
        result = self.client.embeddings.create(input=texts, model=model)
        return [row.embedding for row in result.data]
