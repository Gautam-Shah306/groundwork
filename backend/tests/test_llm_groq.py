"""Unit tests for the Groq adapter and reasoning model handling."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from groq import APIStatusError, APITimeoutError

from app.agent.loop import run_investigation
from app.agent.tools import ToolRegistry
from app.llm.base import LLMMessage, LLMResponse, LLMUsage, ToolCall, ToolSchema
from app.llm.errors import (
    LLMAuthError,
    LLMModelNotFound,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMRequestTooLarge,
    LLMTimeout,
    LLMToolCallFailed,
)
from app.llm.groq import GroqProvider, translate_messages, translate_tool_schemas


def _make_groq_completion(
    *,
    content: str | None = None,
    tool_calls: list[tuple[str, str | dict, str]] | None = None,
    reasoning: str | None = None,
    model: str = "openai/gpt-oss-20b",
    prompt_tokens: int = 150,
    completion_tokens: int = 50,
    total_tokens: int = 200,
) -> SimpleNamespace:
    tc_objects = []
    for idx, item in enumerate(tool_calls or []):
        name = item[0]
        args = item[1]
        cid = item[2] if len(item) > 2 else f"call_{idx}"
        args_str = json.dumps(args) if isinstance(args, dict) else str(args)
        tc_objects.append(
            SimpleNamespace(
                id=cid,
                type="function",
                function=SimpleNamespace(name=name, arguments=args_str),
            )
        )

    msg_dict: dict = {"content": content, "tool_calls": tc_objects or None}
    if reasoning is not None:
        msg_dict["reasoning"] = reasoning
        msg_dict["reasoning_content"] = reasoning

    msg = SimpleNamespace(**msg_dict)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _make_groq_status_error(
    status_code: int,
    message: str = "error",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
) -> APIStatusError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp = httpx.Response(
        status_code=status_code,
        headers=headers or {},
        request=req,
        json=body if body is not None else {"error": {"message": message, "code": None}},
    )
    return APIStatusError(message=message, response=resp, body=body)


def test_groq_adapter_translates_tool_schemas_and_parses_tool_calls() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_completion(
        tool_calls=[("get_response_metrics", {"metric": "first_response_time"}, "call_resp_1")]
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="llama-3.3-70b-versatile",
        timeout_seconds=20,
        max_output_tokens=1000,
        client=mock_client,
    )
    schema = ToolSchema(
        name="get_response_metrics",
        description="Fetch response timing metrics.",
        parameters_schema={"type": "object", "properties": {"metric": {"type": "string"}}},
    )

    resp = provider.generate(
        system="Follow AGENTS.md",
        messages=[LLMMessage(role="user", content="Why are customers waiting?")],
        tools=[schema],
    )

    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.name == "get_response_metrics"
    assert tc.arguments == {"metric": "first_response_time"}
    assert tc.call_id == "call_resp_1"
    assert not tc.arguments_invalid

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.3-70b-versatile"
    assert kwargs["messages"][0] == {"role": "system", "content": "Follow AGENTS.md"}
    assert kwargs["messages"][1] == {"role": "user", "content": "Why are customers waiting?"}
    assert kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_response_metrics",
                "description": "Fetch response timing metrics.",
                "parameters": {"type": "object", "properties": {"metric": {"type": "string"}}},
            },
        }
    ]


def test_groq_adapter_malformed_tool_arguments_flagged_not_raised() -> None:
    mock_client = MagicMock()
    # Malformed JSON string passed as function.arguments
    mock_client.chat.completions.create.return_value = _make_groq_completion(
        tool_calls=[("compute_kpis", "{invalid_json: true,", "call_bad_json")]
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        client=mock_client,
    )

    resp = provider.generate(
        system="System prompt",
        messages=[LLMMessage(role="user", content="run metrics")],
    )

    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.name == "compute_kpis"
    assert tc.arguments == {}
    assert tc.arguments_invalid is True
    assert tc.raw_arguments == "{invalid_json: true,"


def test_loop_returns_structured_error_to_model_for_flagged_invalid_arguments() -> None:
    # First turn returns a malformed tool call; second turn receives structured error and returns final answer
    provider = MagicMock()
    bad_tc = ToolCall(
        name="get_response_metrics",
        arguments={},
        call_id="call_bad_1",
        arguments_invalid=True,
        raw_arguments="{'metric': unquoted_value}",
    )
    from app.llm.base import LLMUsage

    first_response = LLMResponse(
        text="",
        tool_calls=[bad_tc],
        model="openai/gpt-oss-20b",
    )
    final_response = LLMResponse(
        text='{"blocks": [{"type": "finding", "text": "Corrected finding.", "evidence_call_ids": []}]}',
        tool_calls=[],
        model="openai/gpt-oss-20b",
    )
    provider.model_name = "openai/gpt-oss-20b"
    provider.generate.side_effect = [first_response, final_response]

    registry = MagicMock()
    registry.schemas.return_value = []
    result = run_investigation(
        question="Analyze delays",
        provider=provider,
        registry=registry,
    )

    assert result.status == "completed"
    # Verify the tool trace recorded the invalid arguments error
    assert len(result.tool_trace) == 1
    trace_item = result.tool_trace[0]
    assert trace_item.ok is False
    assert trace_item.error is not None
    assert trace_item.error.code == "invalid_arguments"

    # Verify the second call to provider.generate received the tool result message
    second_call_messages = provider.generate.call_args_list[1].kwargs["messages"]
    tool_msg = next((m for m in second_call_messages if m.role == "tool"), None)
    assert tool_msg is not None
    assert tool_msg.tool_call_id == "call_bad_1"
    assert tool_msg.tool_result["ok"] is False
    assert tool_msg.tool_result["error"]["code"] == "invalid_arguments"


def test_groq_adapter_ignores_reasoning_field_and_never_returns_it() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_completion(
        content='{"blocks": [{"type": "finding", "text": "Clear finding.", "evidence_call_ids": []}]}',
        reasoning="I need to think about SLA targets and internal queue structure deeply.",
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        client=mock_client,
    )

    resp = provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="hello")],
    )

    assert "deeply" not in resp.text
    assert "SLA targets" not in resp.text
    assert not hasattr(resp, "reasoning")
    assert not hasattr(resp, "reasoning_content")
    assert resp.text == '{"blocks": [{"type": "finding", "text": "Clear finding.", "evidence_call_ids": []}]}'


def test_groq_adapter_sets_reasoning_effort_only_for_gpt_oss_models() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_completion(content="ans")

    # For openai/gpt-oss-* model: reasoning_effort passed
    gpt_oss_provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        reasoning_effort="low",
        client=mock_client,
    )
    gpt_oss_provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])
    call1_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call1_kwargs["reasoning_effort"] == "low"

    # For non-gpt-oss model: reasoning_effort NOT passed
    mock_client.reset_mock()
    llama_provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="llama-3.3-70b-versatile",
        reasoning_effort="low",
        client=mock_client,
    )
    llama_provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])
    call2_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in call2_kwargs


def test_groq_adapter_uses_max_completion_tokens_and_disables_sdk_retries() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_completion(content="ans")

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_output_tokens=2500,
        client=mock_client,
    )
    provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_completion_tokens"] == 2500
    assert "max_tokens" not in kwargs


def test_groq_adapter_records_token_usage_and_loop_sums_it_per_run() -> None:
    # 2 round trips with token usage: verify sum
    provider = MagicMock()
    provider.model_name = "openai/gpt-oss-20b"
    first_resp = LLMResponse(
        text="",
        tool_calls=[ToolCall(name="get_kpis", arguments={})],
        usage=LLMUsage(input_tokens=100, output_tokens=30, total_tokens=130),
    )
    second_resp = LLMResponse(
        text='{"blocks": [{"type": "finding", "text": "Tokens verified.", "evidence_call_ids": []}]}',
        tool_calls=[],
        usage=LLMUsage(input_tokens=140, output_tokens=60, total_tokens=200),
    )
    provider.generate.side_effect = [first_resp, second_resp]

    from app.agent.tools import ToolResult

    registry = MagicMock()
    registry.schemas.return_value = []
    registry.execute.return_value = ToolResult(
        call_id="call_1",
        tool="get_kpis",
        args={},
        ok=True,
        data={"kpi": 1},
        error=None,
        duration_ms=5,
    )

    result = run_investigation(
        question="Tokens test",
        provider=provider,
        registry=registry,
    )

    assert result.usage["prompt_tokens"] == 240
    assert result.usage["completion_tokens"] == 90
    assert result.usage["total_tokens"] == 330


def test_groq_429_honours_short_retry_after_then_succeeds() -> None:
    mock_client = MagicMock()
    rate_err = _make_groq_status_error(
        429,
        message="Rate limit reached",
        headers={"retry-after": "1.5"},
    )
    mock_client.chat.completions.create.side_effect = [
        rate_err,
        _make_groq_completion(content='{"blocks": []}'),
    ]
    sleeps: list[float] = []

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    resp = provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])
    assert resp.text == '{"blocks": []}'
    assert mock_client.chat.completions.create.call_count == 2
    assert sleeps == [1.5]


def test_groq_429_with_long_retry_after_fails_without_waiting() -> None:
    mock_client = MagicMock()
    rate_err = _make_groq_status_error(
        429,
        message="Rate limit reached: please retry later",
        headers={"retry-after": "45"},
    )
    mock_client.chat.completions.create.side_effect = rate_err
    sleeps: list[float] = []

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(LLMRateLimited) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_rate_limited"
    assert mock_client.chat.completions.create.call_count == 1
    assert sleeps == []


def test_groq_daily_limit_429_maps_to_quota_exhausted_and_is_not_retried() -> None:
    mock_client = MagicMock()
    daily_err = _make_groq_status_error(
        429,
        message="Rate limit reached for model: 500,000 tokens per day limit exceeded",
    )
    mock_client.chat.completions.create.side_effect = daily_err
    sleeps: list[float] = []

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(LLMQuotaExhausted) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_quota_exhausted"
    assert mock_client.chat.completions.create.call_count == 1
    assert sleeps == []


def test_groq_tool_use_failed_retried_once_then_raises_llm_tool_call_failed() -> None:
    mock_client = MagicMock()
    tool_err = _make_groq_status_error(
        400,
        message="Failed to call a function",
        body={"error": {"code": "tool_use_failed", "message": "Failed to call a function"}},
    )
    mock_client.chat.completions.create.side_effect = [tool_err, tool_err]
    sleeps: list[float] = []

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
        base_backoff_seconds=0.25,
    )

    with pytest.raises(LLMToolCallFailed) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_tool_call_failed"
    assert mock_client.chat.completions.create.call_count == 2
    assert sleeps == [0.25]


def test_groq_401_maps_to_auth_error_not_retried() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _make_groq_status_error(401, "Invalid API Key")
    sleeps: list[float] = []

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(LLMAuthError) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_auth_error"
    assert mock_client.chat.completions.create.call_count == 1
    assert sleeps == []


def test_groq_404_maps_to_model_not_found_without_exposing_model_value() -> None:
    secret_model = "super-secret-model-name-v99"
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _make_groq_status_error(
        404, message=f"Model '{secret_model}' not found"
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model=secret_model,
        client=mock_client,
    )

    with pytest.raises(LLMModelNotFound) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_model_not_found"
    assert "LLM_MODEL" in exc_info.value.message
    assert secret_model not in exc_info.value.message


def test_groq_413_maps_to_request_too_large() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _make_groq_status_error(
        413, message="Payload too large"
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        client=mock_client,
    )

    with pytest.raises(LLMRequestTooLarge) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_request_too_large"


def test_groq_timeout_maps_to_llm_timeout() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APITimeoutError(
        request=httpx.Request("POST", "https://api.groq.com")
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        timeout_seconds=22,
        client=mock_client,
    )

    with pytest.raises(LLMTimeout) as exc_info:
        provider.generate(system="sys", messages=[LLMMessage(role="user", content="hi")])

    assert exc_info.value.code == "llm_timeout"
    assert "22s" in exc_info.value.message


def test_groq_adapter_sets_truncated_when_finish_reason_is_length() -> None:
    mock_client = MagicMock()
    first_choice_len = SimpleNamespace(
        message=SimpleNamespace(content="partial output cut off", tool_calls=[]),
        finish_reason="length",
    )
    raw_response_len = SimpleNamespace(
        choices=[first_choice_len],
        model="openai/gpt-oss-20b",
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    mock_client.chat.completions.create.return_value = raw_response_len

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        client=mock_client,
    )
    res_truncated = provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="write a long text")],
    )
    assert res_truncated.truncated is True

    # Test normal finish reason
    first_choice_stop = SimpleNamespace(
        message=SimpleNamespace(content="complete text", tool_calls=[]),
        finish_reason="stop",
    )
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[first_choice_stop],
        model="openai/gpt-oss-20b",
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    res_normal = provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="write normal")],
    )
    assert res_normal.truncated is False


def test_groq_adapter_passes_temperature_when_set() -> None:
    mock_client = MagicMock()
    choice = SimpleNamespace(
        message=SimpleNamespace(content="Classification result", tool_calls=[]),
        finish_reason="stop",
    )
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[choice],
        model="openai/gpt-oss-20b",
        usage=SimpleNamespace(prompt_tokens=40, completion_tokens=20, total_tokens=60),
    )

    provider = GroqProvider(
        api_key="mock_synthetic_key_not_real",
        model="openai/gpt-oss-20b",
        client=mock_client,
    )
    # When temperature=0.0 is explicitly passed
    provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="classify")],
        temperature=0.0,
    )
    call_kwargs0 = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs0["temperature"] == 0.0

    # When temperature=0.5 is passed
    provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="draft")],
        temperature=0.5,
    )
    call_kwargs5 = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs5["temperature"] == 0.5
