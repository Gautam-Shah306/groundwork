"""Provider-neutral LLM exception hierarchy with secret scrubbing."""

from __future__ import annotations

import re
from collections.abc import Sequence

_HEADER_OR_KEY_PATTERNS = (
    re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)(?:bearer\s+)?[^\s,;\"']+"),
    re.compile(r"(?i)\bbearer\s+[^\s,;\"']+"),
    re.compile(r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)[^\s,;\"']+"),
    re.compile(r"(?i)(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[^\s,;\"']+"),
    re.compile(r"(?i)([?&]key=)[^&\s\"']+"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
)


def scrub_secrets(text: str, secrets: Sequence[str] = ()) -> str:
    """Remove API keys, tokens, and auth header values from any error string."""
    cleaned = text
    for secret in secrets:
        token = secret.strip()
        if token:
            cleaned = cleaned.replace(token, "[REDACTED]")
    for pattern in _HEADER_OR_KEY_PATTERNS:
        cleaned = pattern.sub(
            lambda m: f"{m.group(1)}[REDACTED]" if m.lastindex else "[REDACTED]",
            cleaned,
        )
    return cleaned


class LLMError(Exception):
    """Base error for all LLM provider failures."""

    code: str = "llm_provider_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        if code is not None:
            self.code = code
        self.message = scrub_secrets(message, secrets=secrets)
        super().__init__(self.message)


class LLMNotConfigured(LLMError):
    code = "llm_not_configured"


class UnsupportedProvider(LLMError):
    code = "unsupported_provider"


class LLMTimeout(LLMError):
    code = "llm_timeout"


class LLMRateLimited(LLMError):
    code = "llm_rate_limited"


class LLMAuthError(LLMError):
    code = "llm_auth_error"


class LLMQuotaExhausted(LLMError):
    code = "llm_quota_exhausted"
    DEFAULT_MESSAGE = (
        "The LLM provider reports that credits or the daily limit are exhausted for this "
        "API key's project. Check billing and quota, wait for the limit to reset, or use a different key."
    )

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
        *,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE, code=code, secrets=secrets)


class LLMModelNotFound(LLMError):
    code = "llm_model_not_found"
    DEFAULT_MESSAGE = (
        "The configured LLM_MODEL was not found by the provider. "
        "Check the model name in your environment settings."
    )

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
        *,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE, code=code, secrets=secrets)


class LLMRequestTooLarge(LLMError):
    code = "llm_request_too_large"
    DEFAULT_MESSAGE = "The request exceeded the provider's size or token limit for this model."

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
        *,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE, code=code, secrets=secrets)


class LLMOutputTruncated(LLMError):
    code = "llm_output_truncated"
    DEFAULT_MESSAGE = "The analysis was cut off. Shorten the notes or raise LLM_DISCOVERY_MAX_OUTPUT_TOKENS."

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
        *,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE, code=code, secrets=secrets)


class LLMToolCallFailed(LLMError):
    code = "llm_tool_call_failed"
    DEFAULT_MESSAGE = "The model produced an invalid tool call. Try the question again."

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
        *,
        attempted_tool: str | None = None,
        code: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        self.attempted_tool = attempted_tool
        super().__init__(message or self.DEFAULT_MESSAGE, code=code, secrets=secrets)


class LLMProviderError(LLMError):
    code = "llm_provider_error"
