"""Discovery analysis orchestration service with data isolation, repair loop, and version tracking."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.discovery.postprocess import postprocess_brief
from app.discovery.prompts import (
    DISCOVERY_REPAIR_PROMPT,
    DISCOVERY_SYSTEM_PROMPT,
    NOTE_BLOCK_END,
    NOTE_BLOCK_END_ESCAPED,
    NOTE_BLOCK_START,
)
from app.discovery.schema import BriefSections
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMUsage
from app.llm.errors import LLMError, LLMOutputTruncated, scrub_secrets
from app.models import (
    BriefSource,
    BriefVersion,
    DiscoveryAnalysis,
    Engagement,
    InterviewNote,
    ProblemBrief,
    utc_now,
)

logger = logging.getLogger(__name__)

MAX_COMBINED_NOTES_CHARS = 30000
_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    match = _CODE_FENCE_RE.match(cleaned)
    if match:
        return match.group(1).strip()
    return cleaned


def record_brief_version(
    db: Session,
    *,
    engagement_id: int,
    sections: dict[str, Any],
    source: str,
    reason: str,
) -> BriefVersion:
    """Record a new snapshot of brief sections and prune older versions beyond 5."""
    now = utc_now()
    version = BriefVersion(
        engagement_id=engagement_id,
        sections=sections,
        source=source,
        reason=reason,
        saved_at=now,
    )
    db.add(version)
    db.flush()

    # Keep only the 5 newest versions per engagement
    versions = (
        db.scalars(
            select(BriefVersion)
            .where(BriefVersion.engagement_id == engagement_id)
            .order_by(BriefVersion.saved_at.desc(), BriefVersion.id.desc())
        )
        .all()
    )
    if len(versions) > 5:
        for v in versions[5:]:
            db.delete(v)
        db.flush()

    return version


def build_analysis_payload(
    engagement: Engagement,
    notes: list[InterviewNote],
) -> tuple[str, str, int]:
    """Format delimited data block containing ONLY engagement context and selected notes."""
    total_chars = sum(len(n.title or "") + len(n.content or "") for n in notes)
    if total_chars > MAX_COMBINED_NOTES_CHARS:
        raise ValueError(
            f"Combined notes length ({total_chars} characters) exceeds the 30,000 character limit. "
            "Please select fewer notes or trim verbose interview content."
        )

    parts: list[str] = [
        f"Engagement Name: {engagement.name}",
        f"Client Name: {engagement.client_name}",
        f"Industry: {engagement.industry}",
        f"Client Statement: {engagement.client_statement}",
        "",
        "Interview Notes Data:",
    ]

    all_notes_text: list[str] = []
    for note in notes:
        # Neutralize any occurrence of the closing delimiter inside note text
        safe_content = (note.content or "").replace(NOTE_BLOCK_END, NOTE_BLOCK_END_ESCAPED)
        all_notes_text.append(f"{note.title}\n{note.content}")
        start_tag = NOTE_BLOCK_START.format(note_id=note.id, title=note.title)
        parts.append(start_tag)
        parts.append(safe_content)
        parts.append(NOTE_BLOCK_END)

    return "\n".join(parts), "\n".join(all_notes_text), total_chars


def execute_discovery_analysis(
    *,
    db: Session,
    engagement: Engagement,
    notes: list[InterviewNote],
    provider: LLMProvider,
    max_output_tokens: int = 4000,
    api_key_secret: str = "",
) -> DiscoveryAnalysis:
    """Run AI discovery analysis, execute post-processing, and persist DiscoveryAnalysis."""
    if not notes:
        raise ValueError("At least one interview note is required for discovery analysis.")

    prompt_data, raw_notes_text, total_chars = build_analysis_payload(engagement, notes)
    note_ids = [n.id for n in notes]

    messages = [LLMMessage(role="user", content=prompt_data)]
    usage_dict: dict[str, Any] = {}
    model_name = provider.model_name or "llm"

    try:
        response = provider.generate(
            system=DISCOVERY_SYSTEM_PROMPT,
            messages=messages,
            tools=None,
            max_output_tokens=max_output_tokens,
        )
        if response.model:
            model_name = response.model
        if response.usage:
            usage_dict = response.usage.model_dump()

        if response.truncated:
            raise LLMOutputTruncated()

        # Parse JSON
        cleaned = _strip_code_fences(response.text)
        parsed_dict: dict[str, Any] | None = None
        brief_obj: BriefSections | None = None
        try:
            parsed_dict = json.loads(cleaned)
            if isinstance(parsed_dict, dict):
                brief_obj = BriefSections.model_validate(parsed_dict)
        except (json.JSONDecodeError, ValidationError):
            brief_obj = None

        # One repair attempt if initial parse fails
        if brief_obj is None:
            repair_messages = [
                LLMMessage(role="user", content=prompt_data),
                LLMMessage(role="assistant", content=response.text),
                LLMMessage(role="user", content=DISCOVERY_REPAIR_PROMPT),
            ]
            repair_resp = provider.generate(
                system=DISCOVERY_SYSTEM_PROMPT,
                messages=repair_messages,
                tools=None,
                max_output_tokens=max_output_tokens,
            )
            if repair_resp.truncated:
                raise LLMOutputTruncated()
            if repair_resp.usage:
                # Accumulate usage
                usage_dict["total_tokens"] = (usage_dict.get("total_tokens") or 0) + (
                    repair_resp.usage.total_tokens or 0
                )
                usage_dict["input_tokens"] = (usage_dict.get("input_tokens") or 0) + (
                    repair_resp.usage.input_tokens or 0
                )
                usage_dict["output_tokens"] = (usage_dict.get("output_tokens") or 0) + (
                    repair_resp.usage.output_tokens or 0
                )
            rep_cleaned = _strip_code_fences(repair_resp.text)
            try:
                parsed_dict = json.loads(rep_cleaned)
                if isinstance(parsed_dict, dict):
                    brief_obj = BriefSections.model_validate(parsed_dict)
            except Exception as parse_err:
                raise LLMError(
                    f"Model response was not valid JSON conforming to BriefSections: {parse_err}"
                ) from parse_err

        if brief_obj is None:
            raise LLMError("Failed to parse structured brief from model response.")

        # Post-process deterministically
        processed_brief, warnings = postprocess_brief(
            brief_obj,
            client_statement=engagement.client_statement,
            notes_text=raw_notes_text,
            raw_draft=parsed_dict,
        )

        analysis = DiscoveryAnalysis(
            engagement_id=engagement.id,
            note_ids=note_ids,
            status="completed",
            draft=processed_brief.model_dump(mode="json"),
            warnings=warnings,
            error=None,
            model=model_name,
            usage=usage_dict,
            notes_chars=total_chars,
            created_at=utc_now(),
            applied_at=None,
        )
        db.add(analysis)
        db.flush()

        record_audit_event(
            db,
            engagement_id=engagement.id,
            action="analyse_notes",
            entity_type="discovery_analysis",
            entity_id=analysis.id,
            details={
                "note_ids": note_ids,
                "notes_chars": total_chars,
                "status": "completed",
                "warnings_count": len(warnings),
            },
        )
        db.commit()
        db.refresh(analysis)
        return analysis

    except Exception as exc:
        code = getattr(exc, "code", "llm_provider_error")
        msg = scrub_secrets(str(exc), secrets=(api_key_secret,))
        # Never store secret keys or prompt notes in analysis error
        analysis = DiscoveryAnalysis(
            engagement_id=engagement.id,
            note_ids=note_ids,
            status="failed",
            draft=None,
            warnings=[],
            error={"code": code, "message": msg},
            model=model_name,
            usage=usage_dict or None,
            notes_chars=total_chars,
            created_at=utc_now(),
            applied_at=None,
        )
        db.add(analysis)
        db.flush()

        record_audit_event(
            db,
            engagement_id=engagement.id,
            action="analyse_notes",
            entity_type="discovery_analysis",
            entity_id=analysis.id,
            details={
                "note_ids": note_ids,
                "notes_chars": total_chars,
                "status": "failed",
                "error_code": code,
            },
        )
        db.commit()
        db.refresh(analysis)
        raise
