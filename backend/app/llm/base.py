"""Provider-neutral LLM message, tool schema, response, and interface types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolSchema(BaseModel):
    """Provider-neutral tool declaration built from a Pydantic JSON schema."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Provider-neutral tool invocation requested by the model."""

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str = ""
    arguments_invalid: bool = False
    raw_arguments: str = ""


class LLMMessage(BaseModel):
    """Provider-neutral conversation message."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_result: dict[str, Any] | None = None


class LLMUsage(BaseModel):
    """Optional token usage metadata returned by a provider."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMResponse(BaseModel):
    """Provider-neutral response from a single generation round trip."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model: str = ""
    truncated: bool = False


class LLMProvider(ABC):
    """Abstract interface that every concrete LLM adapter must implement."""

    model_name: str = ""

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Execute one model round trip and return a normalized LLMResponse."""
