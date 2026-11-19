"""Unit tests for the provider-neutral LLM layer and Gemini adapter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors as genai_errors

from app.config import Settings
from app.llm import (
    LLMAuthError,
    LLMMessage,
    LLMNotConfigured,
    LLMProviderError,
    LLMRateLimited,
    LLMTimeout,
    ToolSchema,
    UnsupportedProvider,
    get_provider,
)
from app.llm.gemini import GeminiProvider


def _make_gemini_response(
    *,
    text: str | None = None,
    function_calls: list[tuple[str, dict]] | None = None,
    model_version: str = "gemini-2.5-flash",
) -> SimpleNamespace:
    parts = []
    if text is not None:
        parts.append(SimpleNamespace(text=text, function_call=None, thought=False))
    for name, args in function_calls or []:
        parts.append(
            SimpleNamespace(
                text=None,
                function_call=SimpleNamespace(name=name, args=args),
                thought=False,
            )
        )
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))],
        text=text,
        function_calls=[
            SimpleNamespace(name=n, args=a) for n, a in (function_calls or [])
        ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=120,
            candidates_token_count=45,
            total_token_count=165,
        ),
        model_version=model_version,
    )


def test_factory_raises_not_configured_when_key_missing() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_api_key="   ",
        llm_model="gemini-2.5-flash",
    )
    with pytest.raises(LLMNotConfigured) as exc_info:
        get_provider(settings)
    assert exc_info.value.code == "llm_not_configured"
    assert "LLM_API_KEY" in exc_info.value.message


def test_factory_raises_when_model_missing() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_api_key="synthetic-key-not-real",
        llm_model="",
    )
    with pytest.raises(LLMNotConfigured) as exc_info:
        get_provider(settings)
    assert exc_info.value.code == "llm_not_configured"
    assert "LLM_MODEL" in exc_info.value.message


def test_factory_rejects_unknown_provider() -> None:
    for provider in ("openai", "fake", ""):
        settings = Settings(
            _env_file=None,
            llm_provider=provider,
            llm_api_key="synthetic-key-not-real",
            llm_model="some-model",
        )
        with pytest.raises(UnsupportedProvider) as exc_info:
            get_provider(settings)
        assert exc_info.value.code == "unsupported_provider"


def test_gemini_adapter_translates_tool_schemas_and_parses_tool_calls() -> None:
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_gemini_response(
        function_calls=[("get_response_metrics", {"metric": "first_response_time"})]
    )

    provider = GeminiProvider(
        api_key="synthetic-key-not-real",
        model="gemini-2.5-flash",
        timeout_seconds=15,
        max_retries=2,
        max_output_tokens=900,
        client=mock_client,
    )
    tool_schema = ToolSchema(
        name="get_response_metrics",
        description="Return deterministic response timing metrics.",
        parameters_schema={
            "title": "ResponseMetricArgs",
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["first_response_time", "triage_time"],
                }
            },
            "required": ["metric"],
            "additionalProperties": False,
        },
    )

    result = provider.generate(
        system="Use tools before citing figures.",
        messages=[LLMMessage(role="user", content="Why are customers waiting?")],
        tools=[tool_schema],
        max_output_tokens=750,
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_response_metrics"
    assert result.tool_calls[0].arguments == {"metric": "first_response_time"}
    assert result.usage.total_tokens == 165
    assert result.model == "gemini-2.5-flash"

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-flash"
    cfg = call_kwargs["config"]
    assert cfg.max_output_tokens == 750
    assert cfg.system_instruction == "Use tools before citing figures."
    assert len(cfg.tools) == 1
    decls = cfg.tools[0].function_declarations
    assert len(decls) == 1
    assert decls[0].name == "get_response_metrics"
    assert decls[0].parameters_json_schema["type"] == "object"
    assert "metric" in decls[0].parameters_json_schema["properties"]


def test_gemini_adapter_retries_on_rate_limit_then_succeeds() -> None:
    mock_client = MagicMock()
    rate_err = genai_errors.APIError(429, {"error": {"message": "Quota exceeded"}})
    mock_client.models.generate_content.side_effect = [
        rate_err,
        _make_gemini_response(text='{"blocks": []}'),
    ]
    sleeps: list[float] = []

    provider = GeminiProvider(
        api_key="synthetic-key-not-real",
        model="gemini-2.5-flash",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
        base_backoff_seconds=0.5,
    )

    resp = provider.generate(
        system="sys",
        messages=[LLMMessage(role="user", content="hello")],
    )

    assert resp.text == '{"blocks": []}'
    assert mock_client.models.generate_content.call_count == 2
    assert sleeps == [0.5]

    # Exhausting retries raises LLMRateLimited
    mock_client.models.generate_content.reset_mock()
    mock_client.models.generate_content.side_effect = [rate_err, rate_err, rate_err]
    sleeps.clear()
    with pytest.raises(LLMRateLimited) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hello")],
        )
    assert exc_info.value.code == "llm_rate_limited"
    assert mock_client.models.generate_content.call_count == 3
    assert sleeps == [0.5, 1.0]


def test_gemini_adapter_does_not_retry_on_auth_error() -> None:
    mock_client = MagicMock()
    auth_err = genai_errors.APIError(401, {"error": {"message": "API key invalid"}})
    mock_client.models.generate_content.side_effect = auth_err
    sleeps: list[float] = []

    provider = GeminiProvider(
        api_key="synthetic-key-not-real",
        model="gemini-2.5-flash",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(LLMAuthError) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hello")],
        )

    assert exc_info.value.code == "llm_auth_error"
    assert mock_client.models.generate_content.call_count == 1
    assert sleeps == []


def test_gemini_adapter_maps_timeout_to_llm_timeout() -> None:
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = httpx.ReadTimeout("request timed out")
    sleeps: list[float] = []

    provider = GeminiProvider(
        api_key="synthetic-key-not-real",
        model="gemini-2.5-flash",
        timeout_seconds=12,
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(LLMTimeout) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hello")],
        )

    assert exc_info.value.code == "llm_timeout"
    assert "12s" in exc_info.value.message
    assert mock_client.models.generate_content.call_count == 1
    assert sleeps == []


def test_llm_errors_never_contain_api_key() -> None:
    fake_secret = "AIzaSyFakeSecretKeyForUnitTest999888777"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError(
        f"POST https://generativelanguage.googleapis.com?key={fake_secret} "
        f"headers={{'x-goog-api-key': '{fake_secret}', 'Authorization': 'Bearer {fake_secret}'}}"
    )

    provider = GeminiProvider(
        api_key=fake_secret,
        model="gemini-2.5-flash",
        max_retries=0,
        client=mock_client,
    )

    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hello")],
        )

    rendered = f"{exc_info.value.code} {exc_info.value.message} {exc_info.value!s}"
    assert fake_secret not in rendered
    assert "Bearer " not in rendered


def test_factory_returns_groq_adapter_for_groq_provider_case_insensitive() -> None:
    from app.llm.groq import GroqProvider

    for name in ("groq", "GROQ", " GroQ "):
        settings = Settings(
            _env_file=None,
            llm_provider=name,
            llm_api_key="gsk_key",
            llm_model="openai/gpt-oss-20b",
        )
        prov = get_provider(settings)
        assert isinstance(prov, GroqProvider)
        assert prov.model_name == "openai/gpt-oss-20b"


def test_health_llm_configured_true_for_groq_with_key_and_model() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_api_key="gsk_real_key",
        llm_model="openai/gpt-oss-20b",
    )
    assert settings.llm_configured is True


def test_http_402_maps_to_quota_exhausted_and_is_not_retried() -> None:
    from app.llm.errors import LLMQuotaExhausted

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.APIError(
        402, {"error": {"message": "Prepayment credits depleted."}}
    )
    sleeps: list[float] = []
    provider = GeminiProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )
    with pytest.raises(LLMQuotaExhausted) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hi")],
        )
    assert exc_info.value.code == "llm_quota_exhausted"
    assert mock_client.models.generate_content.call_count == 1
    assert sleeps == []


def test_gemini_resource_exhausted_maps_to_quota_exhausted() -> None:
    from app.llm.errors import LLMQuotaExhausted

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.APIError(
        429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "Resource exhausted"}}
    )
    sleeps: list[float] = []
    provider = GeminiProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        max_retries=2,
        client=mock_client,
        sleep_fn=sleeps.append,
    )
    with pytest.raises(LLMQuotaExhausted) as exc_info:
        provider.generate(
            system="sys",
            messages=[LLMMessage(role="user", content="hi")],
        )
    assert exc_info.value.code == "llm_quota_exhausted"
    assert mock_client.models.generate_content.call_count == 1
    assert sleeps == []


def test_all_llm_errors_never_contain_api_key_or_headers() -> None:
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

    secret = "AIzaSyTopSecret1234567890ABC"
    groq_secret = "gsk_supersecretkeyvalue999888"
    msg = f"Failed with {secret} and {groq_secret} headers: Authorization: Bearer {secret} and x-goog-api-key: {secret}"

    for err_cls in (
        LLMError,
        LLMAuthError,
        LLMModelNotFound,
        LLMProviderError,
        LLMQuotaExhausted,
        LLMRateLimited,
        LLMRequestTooLarge,
        LLMTimeout,
        LLMToolCallFailed,
    ):
        err = err_cls(msg, secrets=(secret, groq_secret))
        rendered = f"{err.message} {err!s}"
        assert secret not in rendered
        assert groq_secret not in rendered
        assert "Bearer " not in rendered


def test_assistant_run_persists_quota_error_code_and_message() -> None:
    from app.agent.loop import run_investigation
    from app.llm.errors import LLMQuotaExhausted

    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.generate.side_effect = LLMQuotaExhausted("Project quota exceeded.")
    registry = MagicMock()
    registry.schemas.return_value = []
    result = run_investigation(
        question="Check queue",
        provider=mock_provider,
        registry=registry,
    )
    assert result.status == "failed"
    assert result.error is not None
    assert result.error["code"] == "llm_quota_exhausted"
    assert "Project quota exceeded." in result.error["message"]


def test_usage_column_added_to_existing_agent_runs_table_idempotently() -> None:
    from sqlalchemy import create_engine
    from app.db import ensure_agent_runs_usage_column

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE agent_runs (id INTEGER PRIMARY KEY, question TEXT)"
        )
        conn.commit()

    # First run: adds column
    ensure_agent_runs_usage_column(engine)
    with engine.connect() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agent_runs)").fetchall()]
        assert "usage" in cols

    # Second run: idempotent, must not raise
    ensure_agent_runs_usage_column(engine)
    with engine.connect() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agent_runs)").fetchall()]
        assert "usage" in cols
