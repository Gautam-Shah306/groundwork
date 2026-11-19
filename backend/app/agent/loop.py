"""Single-turn investigation agent loop with strict limits, incremental trace persistence, and grounding checks."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.grounding import (
    AnswerBlock,
    GroundingWarning,
    StructuredAnswer,
    check_grounding,
)
from app.agent.prompts import REPAIR_PROMPT, SYSTEM_PROMPT
from app.agent.tools import ToolError, ToolRegistry, ToolResult
from app.llm.base import LLMMessage, LLMProvider
from app.llm.errors import LLMError

MAX_ROUND_TRIPS = 6
MAX_TOOL_CALLS = 10
OVERALL_TIMEOUT_SECONDS = 60.0

_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL | re.IGNORECASE)


class InvestigationResult(BaseModel):
    """Outcome returned by run_investigation."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    answer_status: Literal["structured", "unstructured", "none"]
    answer_blocks: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[ToolResult] = Field(default_factory=list)
    warnings: list[GroundingWarning] = Field(default_factory=list)
    error: dict[str, str] | None = None
    model: str = ""
    round_trips: int = 0
    duration_ms: int = 0
    usage: dict[str, int] = Field(default_factory=dict)


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    match = _CODE_FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _parse_structured_answer(raw_text: str) -> StructuredAnswer | None:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        return None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    try:
        return StructuredAnswer.model_validate(payload)
    except ValidationError:
        return None


def _tool_result_for_model(result: ToolResult) -> dict[str, Any]:
    """Serialize a ToolResult for the LLM function response payload."""
    payload: dict[str, Any] = {
        "call_id": result.call_id,
        "tool": result.tool,
        "ok": result.ok,
    }
    if result.ok:
        payload["data"] = result.data
        if result.truncated:
            payload["truncated"] = True
            payload["original_row_count"] = result.original_row_count
    else:
        payload["error"] = result.error.model_dump(mode="json") if result.error else {
            "code": "tool_error",
            "message": "Tool call failed.",
        }
    return payload


def run_investigation(
    *,
    question: str,
    provider: LLMProvider,
    registry: ToolRegistry,
    max_round_trips: int = MAX_ROUND_TRIPS,
    max_tool_calls: int = MAX_TOOL_CALLS,
    overall_timeout_seconds: float = OVERALL_TIMEOUT_SECONDS,
    max_output_tokens: int | None = None,
    on_trace_update: Callable[[list[ToolResult]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> InvestigationResult:
    """Execute one single-turn investigation run bounded by round-trip, tool-call, and time limits."""
    started = clock()
    tool_trace: list[ToolResult] = []
    messages: list[LLMMessage] = [LLMMessage(role="user", content=question.strip())]
    schemas = registry.schemas()
    round_trips = 0
    model_used = provider.model_name or ""
    accumulated_usage: dict[str, int] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    def _record_usage(u: Any) -> None:
        if u is not None:
            inp = getattr(u, "input_tokens", None)
            out = getattr(u, "output_tokens", None)
            tot = getattr(u, "total_tokens", None)
            if inp is not None:
                accumulated_usage["prompt_tokens"] += int(inp)
            if out is not None:
                accumulated_usage["completion_tokens"] += int(out)
            if tot is not None:
                accumulated_usage["total_tokens"] += int(tot)
            elif inp is not None or out is not None:
                accumulated_usage["total_tokens"] = (
                    accumulated_usage["prompt_tokens"] + accumulated_usage["completion_tokens"]
                )

    def _elapsed_ms() -> int:
        return int(round((clock() - started) * 1000))

    def _timed_out() -> bool:
        return (clock() - started) >= overall_timeout_seconds

    def _timeout_result() -> InvestigationResult:
        return InvestigationResult(
            status="failed",
            answer_status="none",
            answer_blocks=[],
            tool_trace=tool_trace,
            warnings=[],
            error={
                "code": "overall_timeout",
                "message": (
                    f"The investigation exceeded its {int(overall_timeout_seconds)}s overall timeout. "
                    "Please retry or ask a narrower question."
                ),
            },
            model=model_used,
            round_trips=round_trips,
            duration_ms=_elapsed_ms(),
            usage=dict(accumulated_usage),
        )

    def _limit_result(reason: str) -> InvestigationResult:
        limit_block = AnswerBlock(
            type="limitation",
            text=f"The investigation stopped at its limit ({reason}). Review the tool activity collected so far or narrow your question.",
            evidence_call_ids=[],
        )
        return InvestigationResult(
            status="completed",
            answer_status="structured",
            answer_blocks=[limit_block.model_dump(mode="json")],
            tool_trace=tool_trace,
            warnings=[],
            error=None,
            model=model_used,
            round_trips=round_trips,
            duration_ms=_elapsed_ms(),
            usage=dict(accumulated_usage),
        )

    final_raw_text: str | None = None

    while round_trips < max_round_trips:
        if _timed_out():
            return _timeout_result()

        round_trips += 1
        try:
            response = provider.generate(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=schemas,
                max_output_tokens=max_output_tokens,
            )
            _record_usage(response.usage)
        except LLMError as exc:
            return InvestigationResult(
                status="failed",
                answer_status="none",
                answer_blocks=[],
                tool_trace=tool_trace,
                warnings=[],
                error={"code": exc.code, "message": exc.message},
                model=model_used,
                round_trips=round_trips,
                duration_ms=_elapsed_ms(),
                usage=dict(accumulated_usage),
            )
        except Exception as exc:
            return InvestigationResult(
                status="failed",
                answer_status="none",
                answer_blocks=[],
                tool_trace=tool_trace,
                warnings=[],
                error={
                    "code": "llm_provider_error",
                    "message": f"Investigation failed unexpectedly: {exc}",
                },
                model=model_used,
                round_trips=round_trips,
                duration_ms=_elapsed_ms(),
                usage=dict(accumulated_usage),
            )

        if response.model:
            model_used = response.model

        if _timed_out():
            return _timeout_result()

        if response.tool_calls:
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=list(response.tool_calls),
                )
            )
            hit_tool_cap = False
            for tc in response.tool_calls:
                if len(tool_trace) >= max_tool_calls:
                    hit_tool_cap = True
                    break
                if _timed_out():
                    return _timeout_result()

                call_id = tc.call_id or f"call_{len(tool_trace) + 1}"
                if tc.arguments_invalid:
                    result = ToolResult(
                        call_id=call_id,
                        tool=tc.name,
                        args={},
                        ok=False,
                        error=ToolError(
                            code="invalid_arguments",
                            message=f"Invalid arguments for tool '{tc.name}': Malformed JSON arguments: {tc.raw_arguments}",
                        ),
                        duration_ms=0,
                    )
                else:
                    result = registry.execute(tc.name, tc.arguments)
                    if tc.call_id:
                        result.call_id = tc.call_id

                tool_trace.append(result)
                if on_trace_update is not None:
                    on_trace_update(list(tool_trace))

                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_name=tc.name,
                        tool_call_id=call_id,
                        tool_result=_tool_result_for_model(result),
                    )
                )

                if len(tool_trace) >= max_tool_calls:
                    hit_tool_cap = True
                    break

            if hit_tool_cap:
                return _limit_result("maximum tool calls reached")
            continue

        # Model returned a final response without tool calls
        final_raw_text = response.text
        break

    if final_raw_text is None:
        return _limit_result("maximum model round trips reached")

    parsed = _parse_structured_answer(final_raw_text)

    # One repair attempt if the final response was malformed JSON or violated schema
    if parsed is None:
        if _timed_out():
            return _timeout_result()

        messages.append(LLMMessage(role="assistant", content=final_raw_text))
        messages.append(LLMMessage(role="user", content=REPAIR_PROMPT))
        round_trips += 1
        try:
            repair_resp = provider.generate(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=None,
                max_output_tokens=max_output_tokens,
            )
            _record_usage(repair_resp.usage)
        except LLMError as exc:
            return InvestigationResult(
                status="failed",
                answer_status="none",
                answer_blocks=[],
                tool_trace=tool_trace,
                warnings=[],
                error={"code": exc.code, "message": exc.message},
                model=model_used,
                round_trips=round_trips,
                duration_ms=_elapsed_ms(),
                usage=dict(accumulated_usage),
            )
        if repair_resp.model:
            model_used = repair_resp.model
        parsed = _parse_structured_answer(repair_resp.text)
        if parsed is None:
            raw_kept = (repair_resp.text or final_raw_text).strip()
            return InvestigationResult(
                status="completed",
                answer_status="unstructured",
                answer_blocks=[
                    {
                        "type": "unverified",
                        "text": raw_kept,
                        "evidence_call_ids": [],
                    }
                ],
                tool_trace=tool_trace,
                warnings=[],
                error=None,
                model=model_used,
                round_trips=round_trips,
                duration_ms=_elapsed_ms(),
                usage=dict(accumulated_usage),
            )

    warnings = check_grounding(parsed.blocks, tool_trace)
    return InvestigationResult(
        status="completed",
        answer_status="structured",
        answer_blocks=[b.model_dump(mode="json") for b in parsed.blocks],
        tool_trace=tool_trace,
        warnings=warnings,
        error=None,
        model=model_used,
        round_trips=round_trips,
        duration_ms=_elapsed_ms(),
        usage=dict(accumulated_usage),
    )
