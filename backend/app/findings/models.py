"""Pydantic models for deterministic rule-based diagnostic findings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FindingStrength = Literal["strong", "moderate", "weak", "info"]
FindingStatus = Literal["supported", "insufficient_data"]


class FindingText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["observed_fact", "hypothesis"]
    text: str


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    label: str
    value: float | int | str | None
    unit: str
    n: int = Field(..., ge=0)


class ValidationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    kind: Literal["template_question"] = "template_question"
    finding_id: str | None = None


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    strength: FindingStrength | None = None
    status: FindingStatus
    observation: FindingText
    hypothesis: FindingText
    evidence: list[EvidenceRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validation_questions: list[ValidationQuestion] = Field(default_factory=list)
