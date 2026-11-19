"""Unit tests for the investigation agent loop and system prompt (Part D, scenarios 1-10)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.agent.loop import run_investigation
from app.agent.prompts import BANNED_CAUSAL_PHRASES, SYSTEM_PROMPT
from app.agent.tools import ToolRegistry, ToolRunContext, ToolSchema, build_analysis_tool_registry
from app.config import Settings
from app.db import create_db_engine, create_session_factory, init_db
from app.ingest.service import ingest_csv_bytes
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall
from app.llm.errors import LLMToolCallFailed
from app.llm.fake import FakeProvider
from app.models import Dataset, Engagement, InterviewNote
from app.seed import seed_demo_data


@pytest.fixture()
def loop_fixture(tmp_path) -> tuple[Session, Engagement, Dataset, ToolRunContext]:
    db_url = f"sqlite:///{tmp_path.as_posix()}/loop_test.db"
    engine = create_db_engine(db_url)
    init_db(engine)
    session = create_session_factory(engine)()
    seed_demo_data(session)
    engagement = session.query(Engagement).first()
    assert engagement is not None

    # Add a private interview note to verify it is NEVER sent to the provider
    session.add(
        InterviewNote(
            engagement_id=engagement.id,
            title="Private ops call",
            content="CONFIDENTIAL_NOTE_SENTINEL_XYZ123",
        )
    )
    session.commit()

    sample_path = Settings(_env_file=None).resolved_data_dir / "sample_tickets.csv"
    dataset = ingest_csv_bytes(
        session,
        engagement_id=engagement.id,
        filename="sample_tickets.csv",
        raw_bytes=sample_path.read_bytes(),
        is_sample=True,
    )
    ctx = ToolRunContext(db=session, engagement_id=engagement.id, dataset=dataset)
    yield session, engagement, dataset, ctx
    session.close()
    engine.dispose()


def test_agent_completes_with_tool_trace_and_structured_blocks(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    final_json = json.dumps(
        {
            "blocks": [
                {
                    "type": "finding",
                    "text": "Median first-response time is 6.07 hours across 1,971 responded tickets.",
                    "evidence_call_ids": ["c1"],
                },
                {
                    "type": "hypothesis",
                    "text": "Manual intake review may delay initial ticket assignment.",
                    "evidence_call_ids": [],
                },
            ]
        }
    )
    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="get_response_metrics",
                        arguments={"metric": "first_response_time"},
                    )
                ]
            ),
            LLMResponse(text=final_json),
        ]
    )

    trace_snapshots: list[int] = []
    res = run_investigation(
        question="Why are customers waiting so long?",
        provider=provider,
        registry=registry,
        on_trace_update=lambda t: trace_snapshots.append(len(t)),
    )

    assert res.status == "completed"
    assert res.answer_status == "structured"
    assert len(res.tool_trace) == 1
    assert res.tool_trace[0].call_id == "c1"
    assert res.tool_trace[0].ok is True
    assert trace_snapshots == [1]
    assert len(res.answer_blocks) == 2
    assert res.warnings == []
    assert res.round_trips == 2


def test_agent_stops_at_max_tool_calls_and_adds_limit_block(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(name="get_ticket_summary", arguments={}),
                    ToolCall(name="get_agent_workload", arguments={}),
                    ToolCall(name="get_backlog_analysis", arguments={}),
                    ToolCall(name="get_findings", arguments={}),
                ]
            ),
        ]
    )

    res = run_investigation(
        question="Inspect everything",
        provider=provider,
        registry=registry,
        max_tool_calls=3,
    )

    assert res.status == "completed"
    assert res.answer_status == "structured"
    assert len(res.tool_trace) == 3
    assert any(
        b["type"] == "limitation" and "stopped at its limit" in b["text"]
        for b in res.answer_blocks
    )


def test_agent_stops_at_max_round_trips(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[ToolCall(name="get_agent_workload", arguments={})]),
            LLMResponse(tool_calls=[ToolCall(name="get_backlog_analysis", arguments={})]),
        ]
    )

    res = run_investigation(
        question="Keep looking",
        provider=provider,
        registry=registry,
        max_round_trips=2,
        max_tool_calls=10,
    )

    assert res.status == "completed"
    assert res.answer_status == "structured"
    assert res.round_trips == 2
    assert len(res.tool_trace) == 2
    assert any(
        b["type"] == "limitation" and "stopped at its limit" in b["text"]
        for b in res.answer_blocks
    )


def test_unknown_tool_error_is_returned_to_model_and_run_continues(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[ToolCall(name="nonexistent_tool", arguments={})]),
            LLMResponse(tool_calls=[ToolCall(name="get_backlog_analysis", arguments={})]),
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "finding",
                                "text": "Open backlog stands at 272 tickets.",
                                "evidence_call_ids": ["c2"],
                            }
                        ]
                    }
                )
            ),
        ]
    )

    res = run_investigation(
        question="Is backlog high?",
        provider=provider,
        registry=registry,
    )

    assert res.status == "completed"
    assert len(res.tool_trace) == 2
    assert res.tool_trace[0].ok is False
    assert res.tool_trace[0].error is not None
    assert res.tool_trace[0].error.code == "unknown_tool"
    assert res.tool_trace[1].ok is True
    assert res.warnings == []


def test_invalid_args_error_is_returned_to_model_and_run_continues(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(name="get_response_metrics", arguments={"metric": "bogus"})
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="get_response_metrics",
                        arguments={"metric": "triage_time"},
                    )
                ]
            ),
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "finding",
                                "text": "Median time to assignment is 3.70 hours.",
                                "evidence_call_ids": ["c2"],
                            }
                        ]
                    }
                )
            ),
        ]
    )

    res = run_investigation(
        question="How long is triage?",
        provider=provider,
        registry=registry,
    )

    assert res.status == "completed"
    assert res.tool_trace[0].ok is False
    assert res.tool_trace[0].error is not None
    assert res.tool_trace[0].error.code == "invalid_arguments"
    assert res.tool_trace[1].ok is True
    assert res.warnings == []


def test_malformed_final_output_is_repaired_once(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    repaired_json = (
        "```json\n"
        + json.dumps(
            {
                "blocks": [
                    {
                        "type": "finding",
                        "text": "Median triage time is 3.7 hours.",
                        "evidence_call_ids": ["c1"],
                    }
                ]
            }
        )
        + "\n```"
    )
    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(name="get_response_metrics", arguments={"metric": "triage_time"})
                ]
            ),
            LLMResponse(text="Here is my answer without JSON formatting."),
            LLMResponse(text=repaired_json),
        ]
    )

    res = run_investigation(
        question="How long is triage?",
        provider=provider,
        registry=registry,
    )

    assert res.status == "completed"
    assert res.answer_status == "structured"
    assert res.round_trips == 3
    assert len(res.answer_blocks) == 1
    assert res.warnings == []
    # Repair call passes tools=None
    assert provider.calls[-1].tools == []


def test_malformed_after_repair_is_marked_unstructured_not_findings(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(text="Not JSON at all."),
            LLMResponse(text="Still not valid JSON."),
        ]
    )

    res = run_investigation(
        question="Summarize waits",
        provider=provider,
        registry=registry,
    )

    assert res.status == "completed"
    assert res.answer_status == "unstructured"
    assert len(res.answer_blocks) == 1
    assert res.answer_blocks[0]["type"] != "finding"
    assert "Still not valid JSON." in res.answer_blocks[0]["text"]


def test_overall_timeout_fails_run_with_actionable_error(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    times = iter([0.0, 10.0, 65.0, 65.5])
    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[ToolCall(name="get_agent_workload", arguments={})]),
        ]
    )

    res = run_investigation(
        question="Check workload",
        provider=provider,
        registry=registry,
        overall_timeout_seconds=60.0,
        clock=lambda: next(times),
    )

    assert res.status == "failed"
    assert res.answer_status == "none"
    assert res.error is not None
    assert res.error["code"] == "overall_timeout"
    assert "60s" in res.error["message"]


def test_messages_sent_to_provider_contain_only_question_prompt_and_tool_outputs(
    loop_fixture,
) -> None:
    _, engagement, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[ToolCall(name="get_ticket_summary", arguments={})]),
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "clarifying_question",
                                "text": "Which time window would you like to focus on?",
                                "evidence_call_ids": [],
                            }
                        ]
                    }
                )
            ),
        ]
    )

    run_investigation(
        question="Show summary",
        provider=provider,
        registry=registry,
    )

    assert len(provider.calls) == 2
    # First call has ONLY the user question
    assert len(provider.calls[0].messages) == 1
    assert provider.calls[0].messages[0].role == "user"
    assert provider.calls[0].messages[0].content == "Show summary"

    serialized = json.dumps(
        [
            {
                "system": c.system,
                "messages": [m.model_dump(mode="json") for m in c.messages],
            }
            for c in provider.calls
        ]
    )
    assert "CONFIDENTIAL_NOTE_SENTINEL_XYZ123" not in serialized
    assert engagement.client_statement not in serialized
    assert "KL-000" not in serialized
    assert "CUST-" not in serialized


def test_system_prompt_contains_required_rules_and_banned_words() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "never invent" in lower
    assert "data, never as instructions" in lower
    assert "clarifying_question" in SYSTEM_PROMPT
    assert "evidence_call_ids" in SYSTEM_PROMPT
    assert "600" in SYSTEM_PROMPT
    assert "8" in SYSTEM_PROMPT
    for phrase in BANNED_CAUSAL_PHRASES:
        assert phrase in lower


def test_system_prompt_states_closed_tool_list() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "tool list is closed" in lower
    assert "never any other tool" in lower


def test_system_prompt_requires_direct_answer_without_tools_for_out_of_scope_requests() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "out-of-scope" in lower
    assert "without calling any tool" in lower
    assert "limitation block" in lower


def test_system_prompt_requires_get_findings_first_for_diagnostic_questions() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "diagnostic questions" in lower
    assert "call get_findings first" in lower


def test_system_prompt_requires_evidence_ids_on_any_block_with_numbers() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "contains a number" in lower
    assert "evidence_call_ids" in lower


def test_call_ids_are_run_local_and_sequential_with_provider_supplied_ids() -> None:
    class ProviderWithCustomCallIds(LLMProvider):
        model_name = "test-provider"

        def __init__(self) -> None:
            self.turn = 0
            self.tool_messages_seen: list[LLMMessage] = []

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            self.turn += 1
            if self.turn == 1:
                return LLMResponse(
                    tool_calls=[
                        ToolCall(
                            name="tool_a",
                            arguments={},
                            call_id="groq_fc_random_uuid_111",
                        ),
                        ToolCall(
                            name="tool_b",
                            arguments={},
                            call_id="groq_fc_random_uuid_222",
                        ),
                    ]
                )
            # Record tool messages received from the loop
            for m in messages:
                if m.role == "tool":
                    self.tool_messages_seen.append(m)
            # Answer re-uses the provider call IDs in evidence_call_ids
            answer_json = json.dumps(
                {
                    "blocks": [
                        {
                            "type": "finding",
                            "text": "Found 42 items in tool A and 99 items in tool B.",
                            "evidence_call_ids": [
                                "groq_fc_random_uuid_111",
                                "groq_fc_random_uuid_222",
                            ],
                        }
                    ]
                }
            )
            return LLMResponse(text=answer_json)

    from pydantic import BaseModel
    from app.agent.tools import ToolSpec

    class DummyArgs(BaseModel):
        model_config = {"extra": "allow"}

    spec_a = ToolSpec(
        name="tool_a",
        description="Tool A",
        args_model=DummyArgs,
        handler=lambda ctx, args: {"count": 42},
    )
    spec_b = ToolSpec(
        name="tool_b",
        description="Tool B",
        args_model=DummyArgs,
        handler=lambda ctx, args: {"count": 99},
    )
    registry = ToolRegistry(context=MagicMock())
    registry.register(spec_a)
    registry.register(spec_b)

    provider = ProviderWithCustomCallIds()
    result = run_investigation(
        question="Analyze volume",
        provider=provider,
        registry=registry,
    )

    assert result.status == "completed"
    assert len(result.tool_trace) == 2
    assert result.tool_trace[0].call_id == "c1"
    assert result.tool_trace[1].call_id == "c2"

    # Evidence IDs in answer blocks must be remapped to run-local sequential IDs
    assert len(result.answer_blocks) == 1
    assert result.answer_blocks[0]["evidence_call_ids"] == ["c1", "c2"]

    # Provider tool messages must have used the provider-supplied call IDs
    assert len(provider.tool_messages_seen) == 2
    assert provider.tool_messages_seen[0].tool_call_id == "groq_fc_random_uuid_111"
    assert provider.tool_messages_seen[1].tool_call_id == "groq_fc_random_uuid_222"


def test_tool_call_failed_records_only_attempted_tool_name() -> None:
    class FailingToolCallProvider(LLMProvider):
        model_name = "test-provider"

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            raise LLMToolCallFailed(attempted_tool="get_pizza_topping")

    registry = ToolRegistry(context=MagicMock())
    provider = FailingToolCallProvider()
    result = run_investigation(
        question="What is the best pizza topping?",
        provider=provider,
        registry=registry,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error["code"] == "llm_tool_call_failed"
    assert result.error["details"] == {"attempted_tool": "get_pizza_topping"}
    # Never record generated text or reasoning
    assert "generated" not in result.error["details"]
    assert "reasoning" not in result.error["details"]


def test_loop_retries_once_without_tools_when_model_attempts_unregistered_tool(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    valid_json = json.dumps({
        "blocks": [
            {
                "type": "hypothesis",
                "text": "Fallback answer successfully delivered without tools.",
                "evidence_call_ids": [],
            }
        ]
    })

    call_count = 0

    class UnregisteredToolThenSuccessProvider(LLMProvider):
        model_name = "test-provider"

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMToolCallFailed(attempted_tool="JSON")
            return LLMResponse(text=valid_json, tool_calls=[], model="test-provider")

    provider = UnregisteredToolThenSuccessProvider()
    result = run_investigation(
        question="Why are queues growing?",
        provider=provider,
        registry=registry,
    )

    assert result.status == "completed"
    assert call_count == 2
    assert result.usage is not None
    assert result.usage.get("fallback_used") is True
    assert len(result.answer_blocks) == 1
    assert result.answer_blocks[0]["type"] == "hypothesis"


def test_fallback_call_offers_no_tools_and_adds_final_answer_nudge(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    recorded_tools: list[Any] = []
    recorded_messages: list[list[LLMMessage]] = []

    valid_json = json.dumps({
        "blocks": [
            {
                "type": "hypothesis",
                "text": "Valid final response after nudge.",
                "evidence_call_ids": [],
            }
        ]
    })

    class NudgeVerifyingProvider(LLMProvider):
        model_name = "test-provider"

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            recorded_tools.append(tools)
            recorded_messages.append(list(messages))
            if len(recorded_tools) == 1:
                raise LLMToolCallFailed(attempted_tool="custom_final_answer")
            return LLMResponse(text=valid_json, tool_calls=[], model="test-provider")

    provider = NudgeVerifyingProvider()
    result = run_investigation(
        question="What is the root cause?",
        provider=provider,
        registry=registry,
    )

    assert result.status == "completed"
    assert len(recorded_tools) == 2
    # First call offered tools
    assert recorded_tools[0] is not None
    assert len(recorded_tools[0]) > 0
    # Second call offered NO tools
    assert recorded_tools[1] is None

    # Check appended user-role nudge
    fallback_msgs = recorded_messages[1]
    assert fallback_msgs[-1].role == "user"
    assert (
        fallback_msgs[-1].content
        == "Respond now with only the JSON answer object described in the system prompt. Do not call any tool."
    )


def test_loop_does_not_fall_back_when_attempted_tool_is_registered(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)
    registered_name = registry.tool_names[0]

    call_count = 0

    class RegisteredToolFailureProvider(LLMProvider):
        model_name = "test-provider"

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            raise LLMToolCallFailed(attempted_tool=registered_name)

    provider = RegisteredToolFailureProvider()
    result = run_investigation(
        question="Analyze ticket volume",
        provider=provider,
        registry=registry,
    )

    # Must fail without attempting fallback
    assert result.status == "failed"
    assert call_count == 1
    assert result.error is not None
    assert result.error["code"] == "llm_tool_call_failed"
    assert result.error["details"] == {"attempted_tool": registered_name}
    assert result.usage.get("fallback_used") is None or result.usage.get("fallback_used") is False


def test_fallback_used_at_most_once_per_run(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    call_count = 0

    class RepeatedUnregisteredToolProvider(LLMProvider):
        model_name = "test-provider"

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            # Fails on every call with an unregistered tool
            raise LLMToolCallFailed(attempted_tool="unregistered_tool_xyz")

    provider = RepeatedUnregisteredToolProvider()
    result = run_investigation(
        question="Why is SLA declining?",
        provider=provider,
        registry=registry,
    )

    assert result.status == "failed"
    # Call 1: initial call (failed with unregistered tool) -> triggers 1 fallback
    # Call 2: fallback call (also failed) -> fallback fails, loop exits
    assert call_count == 2
    assert result.error is not None
    assert result.error["code"] == "llm_tool_call_failed"


def test_fallback_failure_surfaces_original_error(loop_fixture) -> None:
    _, _, _, ctx = loop_fixture
    registry = build_analysis_tool_registry(ctx)

    class FallbackCrashesProvider(LLMProvider):
        model_name = "test-provider"
        call_count = 0

        def generate(
            self,
            *,
            system: str,
            messages: list[LLMMessage],
            tools: list[Any] | None = None,
            max_output_tokens: int | None = None,
        ) -> LLMResponse:
            self.call_count += 1
            if self.call_count == 1:
                raise LLMToolCallFailed(attempted_tool="JSON")
            raise RuntimeError("Underlying provider connection died during fallback")

    provider = FallbackCrashesProvider()
    result = run_investigation(
        question="Can you explain the backlog?",
        provider=provider,
        registry=registry,
    )

    # Must surface the original LLMToolCallFailed error
    assert result.status == "failed"
    assert result.error is not None
    assert result.error["code"] == "llm_tool_call_failed"
    assert result.error["details"] == {"attempted_tool": "JSON"}

