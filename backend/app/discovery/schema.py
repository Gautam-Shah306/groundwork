"""Pydantic schemas for problem brief sections and discovery items."""

from __future__ import annotations

import uuid
from typing import Literal
from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _default_id() -> str:
    return uuid.uuid4().hex[:8]


class Item(BaseModel):
    """General discovery item with traceability, quote verification, and status flags."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_default_id)
    text: str = Field(..., max_length=300)
    source_quote: str | None = Field(default=None, max_length=400)
    quote_verified: bool | None = None
    origin: Literal["ai", "human"] = "ai"
    status: Literal["ai_draft", "edited", "confirmed"] = "ai_draft"
    flags: list[str] = Field(default_factory=list)


class KnownFactItem(Item):
    """Known fact item distinguishing client statements from observed facts."""

    type: Literal["client_statement", "observed_fact"] = "client_statement"
    source: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_observed_fact_source(self) -> Self:
        if self.type == "observed_fact" and not self.source.strip():
            raise ValueError("An item with type observed_fact must have a non-empty source.")
        return self


class QuestionItem(BaseModel):
    """Follow-up discovery interview question with lifecycle status and answer text."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_default_id)
    text: str = Field(..., max_length=300)
    status: Literal["open", "asked", "answered"] = "open"
    answer: str = Field(default="", max_length=1000)


class ProblemStatement(BaseModel):
    """Testable problem statement with template compliance, status, and wording flags."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=800)
    status: Literal["ai_draft", "edited", "confirmed"] = "ai_draft"
    flags: list[str] = Field(default_factory=list)


class KpiCandidate(BaseModel):
    """Candidate KPI linked to the deterministic metric registry."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_default_id)
    metric_id: str
    rationale: str = Field(default="", max_length=300)
    status: Literal["ai_draft", "edited", "confirmed"] = "ai_draft"


class BriefSections(BaseModel):
    """Structured problem brief sections conforming to the Groundwork discovery specification."""

    model_config = ConfigDict(extra="forbid")

    context: str = Field(default="", max_length=1500)
    themes: list[Item] = Field(default_factory=list, max_length=8)
    stakeholders: list[Item] = Field(default_factory=list, max_length=8)
    workflow_steps: list[Item] = Field(default_factory=list, max_length=8)
    symptoms: list[Item] = Field(default_factory=list, max_length=8)
    impact: list[Item] = Field(default_factory=list, max_length=8)
    known_facts: list[KnownFactItem] = Field(default_factory=list, max_length=8)
    hypotheses: list[Item] = Field(default_factory=list, max_length=8)
    assumptions: list[Item] = Field(default_factory=list, max_length=8)
    unknowns: list[Item] = Field(default_factory=list, max_length=8)
    follow_up_questions: list[QuestionItem] = Field(default_factory=list, max_length=10)
    problem_statement: ProblemStatement = Field(default_factory=lambda: ProblemStatement(text=""))
    candidate_kpis: list[KpiCandidate] = Field(default_factory=list, max_length=5)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_structures(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if isinstance(d.get("problem_statement"), str):
            d["problem_statement"] = {"text": d["problem_statement"]}
        list_sections = (
            "themes",
            "stakeholders",
            "workflow_steps",
            "symptoms",
            "impact",
            "known_facts",
            "hypotheses",
            "assumptions",
            "unknowns",
            "follow_up_questions",
        )
        for sec in list_sections:
            if sec in d and isinstance(d[sec], list):
                new_list = []
                for item in d[sec]:
                    if isinstance(item, str):
                        new_list.append({"text": item})
                    else:
                        new_list.append(item)
                d[sec] = new_list
        return d
