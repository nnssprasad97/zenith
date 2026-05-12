from .gemini import GeminiProvider
from .groq_provider import GroqProvider
from .openrouter_provider import OpenRouterProvider


class ZenithProviderManager:
    """Multi-provider manager with automatic fallback. Ported from vierisid/jarvis."""

    def __init__(self, config: dict):
        self.providers = []
        llm_config = config.get("llm", {})

        if llm_config.get("gemini", {}).get("api_key"):
            self.providers.append(GeminiProvider(llm_config["gemini"]))

        if llm_config.get("groq", {}).get("api_key"):
            self.providers.append(GroqProvider(llm_config["groq"]))

        if llm_config.get("openrouter", {}).get("api_key"):
            self.providers.append(OpenRouterProvider(llm_config["openrouter"]))

        if not self.providers:
            raise ValueError("No LLM providers configured. Add at least GOOGLE_API_KEY.")

        self.current_provider_index = 0

    async def chat(self, messages: list, tools=None) -> str:
        errors = []
        for provider in self.providers:
            try:
                result = await provider.chat(messages, tools)
                self.current_provider_index = self.providers.index(provider)
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                continue

        raise RuntimeError("All providers failed:\n" + "\n".join(errors))

    @property
    def active_provider(self) -> str:
        return self.providers[self.current_provider_index].name

