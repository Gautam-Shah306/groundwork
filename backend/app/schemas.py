"""Pydantic request and response schemas decoupled from ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    AuditLog,
    BriefSource,
    Engagement,
    EngagementStage,
    InterviewNote,
    ProblemBrief,
)


def _strip_required(value: str, field_name: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters.")
    return cleaned


class EngagementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    client_name: str = Field(..., min_length=1, max_length=120)
    industry: str = Field(default="", max_length=120)
    client_statement: str = Field(default="", max_length=2000)
    stage: EngagementStage = Field(default=EngagementStage.discover)
    is_synthetic: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _strip_required(value, "name", 120)

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str) -> str:
        return _strip_required(value, "client_name", 120)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, value: str) -> str:
        return value.strip()

    @field_validator("client_statement")
    @classmethod
    def validate_client_statement(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 2000:
            raise ValueError("client_statement must be at most 2000 characters.")
        return cleaned


class EngagementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    client_name: str | None = Field(default=None, min_length=1, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    client_statement: str | None = Field(default=None, max_length=2000)
    stage: EngagementStage | None = Field(default=None)
    is_synthetic: bool | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "name", 120)

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "client_name", 120)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("client_statement")
    @classmethod
    def validate_client_statement(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) > 2000:
            raise ValueError("client_statement must be at most 2000 characters.")
        return cleaned


class EngagementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    client_name: str
    industry: str
    client_statement: str
    stage: EngagementStage
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_model(cls, engagement: Engagement) -> EngagementResponse:
        return cls(
            id=engagement.id,
            name=engagement.name,
            client_name=engagement.client_name,
            industry=engagement.industry,
            client_statement=engagement.client_statement,
            stage=engagement.stage,
            is_synthetic=engagement.is_synthetic,
            created_at=engagement.created_at,
            updated_at=engagement.updated_at,
        )


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _strip_required(value, "title", 200)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be empty.")
        return cleaned


class NoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "title", 200)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be empty.")
        return cleaned


class NoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    title: str
    content: str
    created_at: datetime

    @classmethod
    def from_orm_model(cls, note: InterviewNote) -> NoteResponse:
        return cls(
            id=note.id,
            engagement_id=note.engagement_id,
            title=note.title,
            content=note.content,
            created_at=note.created_at,
        )


class BriefUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: dict[str, Any] = Field(default_factory=dict)
    source: BriefSource = Field(default=BriefSource.edited)


class BriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    sections: dict[str, Any]
    source: BriefSource
    updated_at: datetime

    @classmethod
    def from_orm_model(cls, brief: ProblemBrief) -> BriefResponse:
        return cls(
            id=brief.id,
            engagement_id=brief.engagement_id,
            sections=dict(brief.sections),
            source=brief.source,
            updated_at=brief.updated_at,
        )


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int | None
    actor: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_orm_model(cls, entry: AuditLog) -> AuditLogResponse:
        return cls(
            id=entry.id,
            engagement_id=entry.engagement_id,
            actor=entry.actor,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            details=dict(entry.details),
            created_at=entry.created_at,
        )
