from jnaara.config import Settings
from jnaara.llm.gemini import GeminiProvider
from jnaara.llm.groq import GroqProvider
from jnaara.llm.mock import MockLLMProvider
from jnaara.llm.provider import LLMProvider


def create_provider(provider_name: str, model: str, settings: Settings) -> LLMProvider:
    """Instantiate an LLM provider by name according to settings."""
    p_name = provider_name.lower().strip()
    if p_name == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=model)
    elif p_name == "gemini":
        return GeminiProvider(api_key=settings.google_api_key, model=model)
    elif p_name == "mock":
        return MockLLMProvider(name="mock")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}. Expected 'groq', 'gemini', or 'mock'.")


def create_providers(settings: Settings) -> tuple[LLMProvider, LLMProvider]:
    """Create configured primary and secondary providers."""
    primary = create_provider(settings.primary_llm, settings.primary_model, settings)
    secondary = create_provider(settings.secondary_llm, settings.secondary_model, settings)
    return primary, secondary
