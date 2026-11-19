"""Google Gemini adapter using the official google-genai SDK."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

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
    LLMProviderError,
    LLMRateLimited,
    LLMTimeout,
)


def _clean_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Pydantic JSON Schema dict for Gemini parameters_json_schema."""
    if not schema:
        return {"type": "object", "properties": {}}
    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("title", "$schema"):
            continue
        if isinstance(value, dict):
            cleaned[key] = _clean_json_schema(value) if key != "properties" else {
                prop_name: _clean_json_schema(prop_val) if isinstance(prop_val, dict) else prop_val
                for prop_name, prop_val in value.items()
            }
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_json_schema(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    if "type" not in cleaned and "properties" in cleaned:
        cleaned["type"] = "object"
    return cleaned


def translate_tool_schemas(tools: list[ToolSchema] | None) -> list[types.Tool] | None:
    """Convert neutral ToolSchema definitions into google-genai Tool declarations."""
    if not tools:
        return None
    declarations = [
        types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=_clean_json_schema(tool.parameters_schema),
        )
        for tool in tools
    ]
    return [types.Tool(function_declarations=declarations)]


def translate_messages(messages: list[LLMMessage]) -> list[types.Content]:
    """Convert neutral LLMMessage objects into google-genai Content turns.

    Adjacent tool result messages are grouped into a single user Content turn
    so parallel function calls receive matching function responses in one turn.
    """
    contents: list[types.Content] = []
    pending_tool_parts: list[types.Part] = []

    def _flush_tool_parts() -> None:
        if pending_tool_parts:
            contents.append(types.Content(role="user", parts=list(pending_tool_parts)))
            pending_tool_parts.clear()

    for msg in messages:
        if msg.role == "tool":
            payload = msg.tool_result if msg.tool_result is not None else {"result": msg.content}
            pending_tool_parts.append(
                types.Part.from_function_response(
                    name=msg.tool_name or "tool",
                    response=payload,
                )
            )
            continue

        _flush_tool_parts()

        if msg.role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=msg.content)])
            )
        elif msg.role == "assistant":
            parts: list[types.Part] = []
            if msg.content:
                parts.append(types.Part.from_text(text=msg.content))
            for tc in msg.tool_calls:
                parts.append(
                    types.Part.from_function_call(name=tc.name, args=dict(tc.arguments))
                )
            if not parts:
                parts.append(types.Part.from_text(text=""))
            contents.append(types.Content(role="model", parts=parts))

    _flush_tool_parts()
    return contents


def _parse_response(raw: Any, fallback_model: str) -> LLMResponse:
    """Extract normalized text, tool calls, and usage from a google-genai response."""
    text_chunks: list[str] = []
    tool_calls: list[ToolCall] = []

    candidates = getattr(raw, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc is not None and getattr(fc, "name", None):
                raw_args = getattr(fc, "args", None) or {}
                tool_calls.append(
                    ToolCall(
                        name=str(fc.name),
                        arguments=dict(raw_args) if isinstance(raw_args, dict) else {},
                    )
                )
                continue
            part_text = getattr(part, "text", None)
            # Exclude internal thought summaries if present on thinking models
            is_thought = bool(getattr(part, "thought", False))
            if part_text and not is_thought:
                text_chunks.append(str(part_text))

    if not text_chunks and not tool_calls:
        fallback_text = getattr(raw, "text", None)
        if isinstance(fallback_text, str) and fallback_text:
            text_chunks.append(fallback_text)

    if not tool_calls:
        raw_fcs = getattr(raw, "function_calls", None) or []
        for fc in raw_fcs:
            if getattr(fc, "name", None):
                raw_args = getattr(fc, "args", None) or {}
                tool_calls.append(
                    ToolCall(
                        name=str(fc.name),
                        arguments=dict(raw_args) if isinstance(raw_args, dict) else {},
                    )
                )

    usage_meta = getattr(raw, "usage_metadata", None)
    usage = LLMUsage(
        input_tokens=getattr(usage_meta, "prompt_token_count", None) if usage_meta else None,
        output_tokens=getattr(usage_meta, "candidates_token_count", None) if usage_meta else None,
        total_tokens=getattr(usage_meta, "total_token_count", None) if usage_meta else None,
    )
    model_version = getattr(raw, "model_version", None) or fallback_model
    return LLMResponse(
        text="".join(text_chunks).strip(),
        tool_calls=tool_calls,
        usage=usage,
        model=str(model_version),
    )


def _extract_status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    return None


def _is_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return True
    status = _extract_status_code(exc)
    if status in (408, 504):
        return True
    msg = str(exc).lower()
    return "timed out" in msg or "timeout" in msg or "deadline_exceeded" in msg


class GeminiProvider(LLMProvider):
    """Gemini LLM adapter wrapping google.genai.Client."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        max_output_tokens: int = 1500,
        client: Any | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        base_backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self.model_name = model
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._default_max_output_tokens = max(1, int(max_output_tokens))
        self._sleep = sleep_fn
        self._base_backoff = base_backoff_seconds
        self._client = (
            client
            if client is not None
            else genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
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
        if status in (401, 403):
            return LLMAuthError(
                "LLM provider authentication failed. Check that LLM_API_KEY and LLM_MODEL in .env are valid.",
                secrets=secrets,
            )
        if status == 429:
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

    def _should_retry(self, exc: Exception) -> bool:
        if _is_timeout_error(exc):
            return False
        status = _extract_status_code(exc)
        if status is None:
            return False
        # Retry ONLY on rate-limit (429) and transient server errors (5xx except 504 timeout)
        return status == 429 or (500 <= status < 600 and status != 504)

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        token_cap = (
            max_output_tokens
            if max_output_tokens is not None
            else self._default_max_output_tokens
        )
        gemini_tools = translate_tool_schemas(tools)
        contents = translate_messages(messages)

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=token_cap,
            temperature=0.0,
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                raw = self._client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                return _parse_response(raw, fallback_model=self.model_name)
            except (genai_errors.APIError, Exception) as exc:
                last_exc = exc
                if attempt < self._max_retries and self._should_retry(exc):
                    delay = self._base_backoff * (2**attempt)
                    self._sleep(delay)
                    continue
                raise self._map_exception(exc) from None

        assert last_exc is not None
        raise self._map_exception(last_exc) from None
