"""Groq LLM provider adapter using the official groq Python SDK."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from groq import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    Groq,
)

from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolSchema,
)
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMModelNotFound,
    LLMProviderError,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMRequestTooLarge,
    LLMTimeout,
    LLMToolCallFailed,
)


def translate_tool_schemas(tools: list[ToolSchema] | None) -> list[dict[str, Any]] | None:
    """Translate provider-neutral ToolSchemas into OpenAI/Groq function tool declarations."""
    if not tools:
        return None
    translated: list[dict[str, Any]] = []
    for tool in tools:
        translated.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema or {"type": "object", "properties": {}},
                },
            }
        )
    return translated


def translate_messages(
    system: str,
    messages: list[LLMMessage],
) -> list[dict[str, Any]]:
    """Translate provider-neutral LLMMessages into OpenAI/Groq chat completion messages."""
    result: list[dict[str, Any]] = []
    if system.strip():
        result.append({"role": "system", "content": system.strip()})

    for msg in messages:
        if msg.role == "user":
            result.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            if msg.tool_calls:
                tc_payload = []
                for tc in msg.tool_calls:
                    arguments_str = (
                        tc.raw_arguments
                        if tc.arguments_invalid
                        else json.dumps(tc.arguments)
                    )
                    tc_payload.append(
                        {
                            "id": tc.call_id or f"call_{tc.name}",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": arguments_str,
                            },
                        }
                    )
                result.append(
                    {
                        "role": "assistant",
                        "content": msg.content or None,
                        "tool_calls": tc_payload,
                    }
                )
            else:
                result.append({"role": "assistant", "content": msg.content})
        elif msg.role == "tool":
            content_str = (
                json.dumps(msg.tool_result)
                if msg.tool_result is not None
                else msg.content
            )
            call_id = msg.tool_call_id or (
                msg.tool_result.get("call_id")
                if isinstance(msg.tool_result, dict)
                else None
            ) or f"call_{msg.tool_name or '1'}"
            tool_entry: dict[str, Any] = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": content_str,
            }
            if msg.tool_name:
                tool_entry["name"] = msg.tool_name
            result.append(tool_entry)

    return result


def _parse_response(raw: Any, fallback_model: str) -> LLMResponse:
    """Extract text, tool calls, and usage from a Groq chat completion object."""
    choices = getattr(raw, "choices", None) or []
    if not choices:
        return LLMResponse(text="", tool_calls=[], usage=LLMUsage(), model=fallback_model)

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None:
        return LLMResponse(text="", tool_calls=[], usage=LLMUsage(), model=fallback_model)

    # Ignore reasoning / reasoning_content entirely - never expose or persist
    text_content = getattr(message, "content", "") or ""

    tool_calls: list[ToolCall] = []
    raw_calls = getattr(message, "tool_calls", None) or []
    for raw_tc in raw_calls:
        fn = getattr(raw_tc, "function", None)
        if fn is None:
            continue
        name = getattr(fn, "name", "")
        call_id = getattr(raw_tc, "id", "") or f"call_{name}"
        raw_args = getattr(fn, "arguments", "")

        if isinstance(raw_args, dict):
            parsed_args = raw_args
            is_invalid = False
            raw_str = ""
        elif isinstance(raw_args, str):
            raw_str = raw_args
            try:
                decoded = json.loads(raw_args)
                if isinstance(decoded, dict):
                    parsed_args = decoded
                    is_invalid = False
                else:
                    parsed_args = {}
                    is_invalid = True
            except Exception:
                parsed_args = {}
                is_invalid = True
        else:
            raw_str = str(raw_args)
            parsed_args = {}
            is_invalid = True

        tool_calls.append(
            ToolCall(
                name=name,
                arguments=parsed_args,
                call_id=call_id,
                arguments_invalid=is_invalid,
                raw_arguments=raw_str,
            )
        )

    usage_meta = getattr(raw, "usage", None)
    usage = LLMUsage(
        input_tokens=getattr(usage_meta, "prompt_tokens", None) if usage_meta else None,
        output_tokens=getattr(usage_meta, "completion_tokens", None) if usage_meta else None,
        total_tokens=getattr(usage_meta, "total_tokens", None) if usage_meta else None,
    )

    model_version = getattr(raw, "model", None) or fallback_model
    finish_reason = getattr(first_choice, "finish_reason", None)
    truncated = (finish_reason == "length")
    return LLMResponse(
        text=text_content.strip(),
        tool_calls=tool_calls,
        usage=usage,
        model=str(model_version),
        truncated=truncated,
    )


def _extract_status_code(exc: Exception) -> int | None:
    for attr in ("status_code", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    return None


def _extract_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) if response else None
    if not headers or not hasattr(headers, "get"):
        return None

    # retry-after-ms takes precedence if present
    retry_ms = headers.get("retry-after-ms")
    if retry_ms:
        try:
            return float(retry_ms) / 1000.0
        except (ValueError, TypeError):
            pass

    retry_sec = headers.get("retry-after")
    if retry_sec:
        try:
            return float(retry_sec)
        except (ValueError, TypeError):
            pass

    return None


def _is_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException, APITimeoutError)):
        return True
    status = _extract_status_code(exc)
    if status in (408, 504):
        return True
    msg = str(exc).lower()
    return "timed out" in msg or "timeout" in msg or "deadline_exceeded" in msg


def _is_daily_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    body = getattr(exc, "body", None)
    body_str = json.dumps(body).lower() if isinstance(body, dict) else ""
    daily_keywords = ("tokens per day", "requests per day", "per day", "tpd", "rpd", "day limit")
    return any(kw in msg or kw in body_str for kw in daily_keywords)


def _is_tool_use_failed(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict) and err.get("code") == "tool_use_failed":
            return True
    return "tool_use_failed" in str(exc).lower()


def _extract_attempted_tool(exc: Exception) -> str | None:
    """Extract attempted tool name if exposed by the provider error, never generated text or reasoning."""
    body = getattr(exc, "body", None)
    candidates: list[str] = []
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict):
            failed_gen = err.get("failed_generation")
            if isinstance(failed_gen, str):
                candidates.append(failed_gen)
            msg = err.get("message")
            if isinstance(msg, str):
                candidates.append(msg)
    candidates.append(str(exc))

    for text in candidates:
        m = re.search(r'["\']name["\']\s*:\s*["\']([a-zA-Z0-9_-]+)["\']', text)
        if m:
            return m.group(1)
        m = re.search(r'(?:tool|function)\s*[:= ]\s*["\']?([a-zA-Z0-9_-]+)["\']?', text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


class GroqProvider(LLMProvider):
    """Groq LLM adapter wrapping the official groq SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        max_output_tokens: int = 2500,
        reasoning_effort: str = "low",
        client: Any | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        base_backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self.model_name = model
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._default_max_output_tokens = max(1, int(max_output_tokens))
        self._reasoning_effort = reasoning_effort or "low"
        self._sleep = sleep_fn
        self._base_backoff = base_backoff_seconds
        self._client = (
            client
            if client is not None
            else Groq(
                api_key=api_key,
                timeout=float(self._timeout_seconds),
                max_retries=0,
            )
        )

    def _map_exception(self, exc: Exception) -> Exception:
        secrets = (self._api_key,)
        if _is_timeout_error(exc):
            return LLMTimeout(
                f"The LLM request timed out after {self._timeout_seconds}s. Please try again.",
                secrets=secrets,
            )

        status = _extract_status_code(exc)
        msg = str(exc).lower()

        if status == 402:
            return LLMQuotaExhausted(secrets=secrets)
        if status == 404:
            return LLMModelNotFound(secrets=secrets)
        if status == 413:
            return LLMRequestTooLarge(secrets=secrets)
        if status in (401, 403):
            if "resource_exhausted" in msg or "quota" in msg:
                return LLMQuotaExhausted(secrets=secrets)
            return LLMAuthError(
                "LLM provider authentication failed. Check that LLM_API_KEY in .env is valid.",
                secrets=secrets,
            )
        if status == 429:
            if _is_daily_limit(exc):
                return LLMQuotaExhausted(secrets=secrets)
            retry_after = _extract_retry_after(exc)
            if retry_after is not None and retry_after > 20.0:
                return LLMRateLimited(
                    f"LLM provider rate limit exceeded. Retry after {int(retry_after)}s.",
                    secrets=secrets,
                )
            return LLMRateLimited(
                "LLM provider rate limit reached. Wait a moment and retry your question.",
                secrets=secrets,
            )
        if status is not None and 400 <= status < 500:
            return LLMProviderError(
                f"LLM provider rejected the request (HTTP {status}). Check LLM_MODEL and request settings.",
                secrets=secrets,
            )
        if status is not None and status >= 500:
            return LLMProviderError(
                f"LLM provider returned a server error (HTTP {status}). Please retry shortly.",
                secrets=secrets,
            )
        return LLMProviderError(
            f"LLM provider request failed: {exc}",
            secrets=secrets,
        )

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        token_cap = (
            max_output_tokens
            if max_output_tokens is not None
            else self._default_max_output_tokens
        )
        chat_messages = translate_messages(system, messages)
        chat_tools = translate_tool_schemas(tools)

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": chat_messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = 0.0
        if chat_tools:
            kwargs["tools"] = chat_tools

        # gpt-oss reasoning model handling
        if self.model_name.lower().startswith("openai/gpt-oss"):
            kwargs["reasoning_effort"] = self._reasoning_effort
            kwargs["max_completion_tokens"] = token_cap
        else:
            kwargs["max_tokens"] = token_cap

        last_exc: Exception | None = None
        tool_use_retried = False

        attempt = 0
        while attempt <= self._max_retries:
            try:
                raw_resp = self._client.chat.completions.create(**kwargs)
                return _parse_response(raw_resp, fallback_model=self.model_name)
            except Exception as exc:
                last_exc = exc
                secrets = (self._api_key,)
                status = _extract_status_code(exc)

                if _is_timeout_error(exc):
                    raise self._map_exception(exc) from None

                # 400 with tool_use_failed: retry ONCE, then raise LLMToolCallFailed
                if status == 400 and _is_tool_use_failed(exc):
                    if not tool_use_retried:
                        tool_use_retried = True
                        self._sleep(self._base_backoff)
                        continue
                    attempted_tool = _extract_attempted_tool(exc)
                    raise LLMToolCallFailed(attempted_tool=attempted_tool, secrets=secrets) from None

                # Non-retriable client errors
                if status in (401, 402, 404, 413):
                    raise self._map_exception(exc) from None

                if status == 403:
                    raise self._map_exception(exc) from None

                # 429 rate limit
                if status == 429:
                    if _is_daily_limit(exc):
                        raise LLMQuotaExhausted(secrets=secrets) from None

                    retry_after = _extract_retry_after(exc)
                    if retry_after is not None:
                        if retry_after > 20.0:
                            raise self._map_exception(exc) from None
                        if attempt < self._max_retries:
                            attempt += 1
                            self._sleep(retry_after)
                            continue
                        raise self._map_exception(exc) from None
                    else:
                        if attempt < self._max_retries:
                            delay = self._base_backoff * (2**attempt)
                            attempt += 1
                            self._sleep(delay)
                            continue
                        raise self._map_exception(exc) from None

                # 5xx server errors
                if status is not None and 500 <= status < 600 and status != 504:
                    if attempt < self._max_retries:
                        delay = self._base_backoff * (2**attempt)
                        attempt += 1
                        self._sleep(delay)
                        continue

                raise self._map_exception(exc) from None

        assert last_exc is not None
        raise self._map_exception(last_exc) from None
