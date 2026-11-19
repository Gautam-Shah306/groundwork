"""Factory resolving the configured LLMProvider from Settings."""

from __future__ import annotations

from app.config import SUPPORTED_LLM_PROVIDERS, Settings
from app.llm.base import LLMProvider
from app.llm.errors import LLMNotConfigured, UnsupportedProvider
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider


def get_provider(settings: Settings) -> LLMProvider:
    """Instantiate the configured LLMProvider or raise a structured configuration error."""
    provider_name = settings.llm_provider.strip().lower()
    if provider_name not in SUPPORTED_LLM_PROVIDERS:
        supported_list = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
        raise UnsupportedProvider(
            f"Unsupported LLM_PROVIDER '{provider_name or '(empty)'}'. Supported providers: {supported_list}."
        )

    api_key = settings.llm_api_key.strip()
    if not api_key:
        raise LLMNotConfigured(
            "Assistant is not configured: set LLM_API_KEY and LLM_MODEL in your local .env file and restart the backend."
        )

    model = settings.llm_model.strip()
    if not model:
        raise LLMNotConfigured(
            "Assistant is not configured: LLM_MODEL is empty. Set LLM_MODEL in your local .env file and restart the backend."
        )

    if provider_name == "groq":
        return GroqProvider(
            api_key=api_key,
            model=model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_output_tokens=settings.llm_max_output_tokens,
            reasoning_effort=settings.llm_reasoning_effort,
        )

    return GeminiProvider(
        api_key=api_key,
        model=model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
    )
