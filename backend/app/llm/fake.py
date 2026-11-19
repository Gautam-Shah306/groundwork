"""Deterministic scripted provider for unit and API tests (never env-selectable)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolSchema


@dataclass
class RecordedCall:
    """Snapshot of a single call made to FakeProvider.generate."""

    system: str
    messages: list[LLMMessage]
    tools: list[ToolSchema]
    max_output_tokens: int | None


class FakeProvider(LLMProvider):
    """Plays back a scripted list of LLMResponse objects or exceptions."""

    def __init__(
        self,
        responses: Sequence[LLMResponse | Exception],
        *,
        model_name: str = "fake-test-model",
    ) -> None:
        self._responses: list[LLMResponse | Exception] = list(responses)
        self.model_name = model_name
        self.calls: list[RecordedCall] = []

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(
            RecordedCall(
                system=system,
                messages=[m.model_copy(deep=True) for m in messages],
                tools=[t.model_copy(deep=True) for t in (tools or [])],
                max_output_tokens=max_output_tokens,
            )
        )
        if not self._responses:
            raise AssertionError("FakeProvider received more calls than scripted responses.")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        if not nxt.model:
            return nxt.model_copy(update={"model": self.model_name})
        return nxt
