"""Structured Pydantic result model for deterministic operational metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    title: str
    definition: str
    unit: str
    scope: str
    n_included: int = Field(..., ge=0)
    n_excluded: int = Field(..., ge=0)
    exclusions: dict[str, int] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    data: Any
    notes: list[str] = Field(default_factory=list)
    as_of: datetime | None = None
