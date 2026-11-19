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


class LLMProviderError(LLMError):
    code = "llm_provider_error"
