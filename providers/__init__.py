def create_provider(name, api_key="", base_url=None):
    name = name.lower()
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(api_key, base_url)
    if name == "deepseek":
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(api_key, base_url or "https://api.deepseek.com")
    if name == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider(api_key, base_url)
    if name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(api_key, base_url)
    if name == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(base_url or "http://localhost:11434", api_key)
    if name == "openrouter":
        from .openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(api_key, base_url or "https://openrouter.ai/api/v1")
    raise ValueError(f"Unknown provider: {name}")
