from .base import Provider, ProviderResponse


class ClaudeProvider(Provider):
    def __init__(self, api_key, base_url=None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)

    def _split(self, messages):
        system = "\n".join(x["content"] for x in messages if x["role"] == "system")
        return system, [x for x in messages if x["role"] != "system"]

    def call(self, messages, model, temperature, max_tokens):
        system, chat = self._split(messages)
        r = self.client.messages.create(model=model, system=system, messages=chat, temperature=temperature, max_tokens=max_tokens)
        if r.stop_reason in {"max_tokens", "model_context_window_exceeded"}:
            raise RuntimeError("Incomplete model output: output/context limit reached")
        return ProviderResponse("".join(x.text for x in r.content), r.usage.input_tokens, r.usage.output_tokens)

    def stream(self, messages, model, temperature, max_tokens):
        system, chat = self._split(messages)
        with self.client.messages.stream(model=model, system=system, messages=chat, temperature=temperature, max_tokens=max_tokens) as stream:
            yield from stream.text_stream

    def estimate_cost(self, input_tokens, output_tokens):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": (input_tokens * 3 + output_tokens * 15) / 1_000_000}
