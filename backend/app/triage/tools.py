"""Pydantic-validated deterministic tool functions for the Support Triage pipeline.

Non-negotiable rules:
- Trace arguments NEVER contain ticket text: store lengths only (body_chars, subject_chars).
- ToolResult conforms to the app standard envelope with run-local IDs (c1, c2, c3, c4).
- record_human_decision is an API-only action and is NOT in any tool registry (R3).
- Neither these nor any triage tools are registered with the Prompt 6 investigation agent.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import ToolError, ToolResult
from app.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.llm.errors import LLMError, LLMOutputTruncated, LLMRateLimited, LLMTimeout
from app.models import ProposalStatus, TriageProposal
from app.text_utils import compute_ticket_hash, neutralize_delimiter, verify_quote
from app.triage.config import TriageConfig
from app.triage.priority import PriorityDecision, evaluate_priority
from app.triage.prompts import (
    ALLOWED_PLACEHOLDERS,
    CLASSIFICATION_REPAIR_PROMPT,
    DRAFTING_REPAIR_PROMPT,
    OVERPROMISE_WORDS,
    build_classification_system_prompt,
    build_drafting_system_prompt,
    extract_policy_headings,
)
from app.triage.schema import (
    ClassificationOutput,
    ClassificationSignal,
    DraftOutput,
    ReviewFlag,
)

logger = logging.getLogger(__name__)

# Identifier regex (e.g. KL-12345)
IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z]{2,4}-\d{3,6}\b")
# Bracketed placeholder regex
PLACEHOLDER_PATTERN = re.compile(r"\[[A-Za-z0-9_]+\]")
# Contact details: email, phone, url
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
URL_PATTERN = re.compile(r"https?://[^\s]+|www\.[^\s]+")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
        elif len(lines) >= 1:
            cleaned = "\n".join(lines[1:]).strip()
    return cleaned


def _log_validation_error(stage: str, exc: ValidationError) -> None:
    """Log Pydantic error locations and types to server log only, NEVER values or model text."""
    err_summary = [{"loc": list(err.get("loc", ())), "type": err.get("type", "")} for err in exc.errors()]
    logger.warning("%s validation failure: %s", stage, err_summary)


def tool_classify_ticket(
    call_id: str,
    *,
    subject: str | None,
    body: str,
    channel: str,
    provider: LLMProvider,
    config: TriageConfig,
    max_output_tokens: int | None = None,
) -> tuple[ToolResult, ClassificationOutput | None, list[ReviewFlag], dict[str, Any]]:
    """Execute classification and signal extraction step with one repair retry."""
    t0 = time.time()
    subject_safe = neutralize_delimiter(subject or "", "</ticket>")
    body_safe = neutralize_delimiter(body, "</ticket>")
    ticket_payload = f"<ticket>\nChannel: {channel}\nSubject: {subject_safe}\nBody:\n{body_safe}\n</ticket>"

    system_prompt = build_classification_system_prompt(config)
    messages = [LLMMessage(role="user", content=ticket_payload)]

    trace_args = {
        "subject_chars": len(subject or ""),
        "body_chars": len(body),
        "channel": channel,
    }

    try:
        response = provider.generate(
            system=system_prompt,
            messages=messages,
            tools=None,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
        )
        if response.truncated:
            raise LLMOutputTruncated("Classification output truncated by token limit.")

        raw_text = _strip_code_fences(response.text)
        try:
            data = json.loads(raw_text)
            parsed = ClassificationOutput.model_validate(data)
        except Exception as exc:
            if isinstance(exc, ValidationError):
                _log_validation_error("Classification", exc)
            # One repair attempt
            logger.info("Classification output invalid JSON; attempting single repair")
            repair_messages = list(messages) + [
                LLMMessage(role="assistant", content=response.text),
                LLMMessage(role="user", content=CLASSIFICATION_REPAIR_PROMPT),
            ]
            repair_resp = provider.generate(
                system=system_prompt,
                messages=repair_messages,
                tools=None,
                max_output_tokens=max_output_tokens,
                temperature=0.0,
            )
            if repair_resp.truncated:
                raise LLMOutputTruncated("Classification repair output truncated.")
            repaired_text = _strip_code_fences(repair_resp.text)
            try:
                repaired_data = json.loads(repaired_text)
                parsed = ClassificationOutput.model_validate(repaired_data)
            except ValidationError as val_exc:
                _log_validation_error("Classification repair", val_exc)
                raise

        # Post-processing flags on classification
        flags: list[ReviewFlag] = []
        known_categories = {c.id for c in config.categories}
        known_signals = set(config.signals.keys())

        # Validate category in vocabulary
        if parsed.category not in known_categories:
            raise ValueError(f"Model returned invalid category '{parsed.category}'.")

        # Secondary equals primary check
        if parsed.secondary_category and parsed.secondary_category == parsed.category:
            parsed.secondary_category = None
            flags.append(
                ReviewFlag(
                    code="secondary_equals_primary",
                    message="Secondary category matched primary category and was set to null.",
                    where="secondary_category",
                )
            )
        elif parsed.secondary_category and parsed.secondary_category not in known_categories:
            flags.append(
                ReviewFlag(
                    code="unknown_secondary_category",
                    message=f"Secondary category '{parsed.secondary_category}' is not in vocabulary.",
                    where="secondary_category",
                )
            )
            parsed.secondary_category = None

        # Process signals
        valid_signals: list[ClassificationSignal] = []
        for s in parsed.signals:
            if s.signal not in known_signals:
                flags.append(
                    ReviewFlag(
                        code="unknown_signal_dropped",
                        message=f"Signal '{s.signal}' is not in the priority rules taxonomy and was dropped.",
                        where="signals",
                    )
                )
                continue

            q = (s.source_quote or "").strip()
            if not q:
                s.quote_verified = False
                flags.append(
                    ReviewFlag(
                        code="signal_without_quote",
                        message=f"Signal '{s.signal}' was returned without a supporting quote.",
                        where="signals",
                    )
                )
            else:
                verified = verify_quote(q, body) or (bool(subject) and verify_quote(q, subject or ""))
                s.quote_verified = verified
                if not verified:
                    flags.append(
                        ReviewFlag(
                            code="signal_quote_not_found",
                            message=f"Quote for signal '{s.signal}' could not be verified in ticket.",
                            where="signals",
                        )
                    )

            valid_signals.append(s)

        parsed.signals = valid_signals
        if not parsed.signals:
            flags.append(
                ReviewFlag(
                    code="no_signals_extracted",
                    message="No priority signals were extracted from this ticket.",
                    where="signals",
                )
            )

        # High-stakes signal unverified check
        high_stakes_signals = {
            "legal_or_chargeback_threat",
            "payment_charged_twice",
            "payment_deducted_order_failed",
            "item_damaged_or_defective",
            "wrong_item_received",
            "delivery_delayed_over_3_days",
            "explicit_urgency",
        }
        for s in parsed.signals:
            if s.signal in high_stakes_signals and not s.quote_verified:
                flags.append(
                    ReviewFlag(
                        code="high_stakes_signal_unverified",
                        message=f"High-stakes signal '{s.signal}' does not have a verified source quote.",
                        where="signals",
                    )
                )

        dur_ms = int(round((time.time() - t0) * 1000))
        result = ToolResult(
            call_id=call_id,
            tool="classify_ticket",
            args=trace_args,
            ok=True,
            data={
                "category": parsed.category,
                "secondary_category": parsed.secondary_category,
                "signals_count": len(parsed.signals),
                "flags_count": len(flags),
            },
            error=None,
            duration_ms=dur_ms,
        )
        usage = {
            "prompt_tokens": getattr(response.usage, "input_tokens", 0) if response.usage else 0,
            "completion_tokens": getattr(response.usage, "output_tokens", 0) if response.usage else 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
        }
        return result, parsed, flags, usage

    except (LLMOutputTruncated, LLMTimeout, LLMRateLimited):
        raise
    except Exception as exc:
        dur_ms = int(round((time.time() - t0) * 1000))
        err_msg = str(exc)
        code = getattr(exc, "code", "classification_failed")
        result = ToolResult(
            call_id=call_id,
            tool="classify_ticket",
            args=trace_args,
            ok=False,
            error=ToolError(code=code, message=err_msg),
            duration_ms=dur_ms,
        )
        return result, None, [], {}


def tool_recommend_priority(
    call_id: str,
    *,
    signals: list[str],
    category: str,
    config: TriageConfig,
) -> tuple[ToolResult, PriorityDecision, str, str, bool]:
    """Deterministically compute priority, rule definition, and queue routing (R1, R4)."""
    t0 = time.time()
    trace_args = {"signals_count": len(signals), "category": category}

    decision = evaluate_priority(signals, config=config)

    # Resolve rule definition in plain language
    rule_definition: str = ""
    for r in config.rules:
        if r.id == decision.rule_id:
            rule_definition = r.description
            break
    if not rule_definition and decision.rule_id == config.default_priority.rule_id:
        rule_definition = "Default priority assigned when no specific rule conditions are met."

    # Resolve target queue
    category_cfg = next((c for c in config.categories if c.id == category), None)
    base_queue = category_cfg.queue if category_cfg else "General"

    if decision.queue_override:
        target_queue = decision.queue_override
        escalation = decision.queue_override == "Escalations"
    else:
        target_queue = base_queue
        escalation = False

    dur_ms = int(round((time.time() - t0) * 1000))
    result = ToolResult(
        call_id=call_id,
        tool="recommend_priority",
        args=trace_args,
        ok=True,
        data={
            "priority": decision.priority,
            "queue": target_queue,
            "rule_id": decision.rule_id,
            "rule_definition": rule_definition,
            "escalation": escalation,
        },
        error=None,
        duration_ms=dur_ms,
    )
    return result, decision, rule_definition, target_queue, escalation


def tool_draft_ticket_response(
    call_id: str,
    *,
    subject: str | None,
    body: str,
    channel: str,
    category: str,
    priority: str,
    policy_text: str,
    provider: LLMProvider,
    max_output_tokens: int | None = None,
) -> tuple[ToolResult, DraftOutput | None, list[ReviewFlag], dict[str, Any]]:
    """Execute response drafting grounded in policy and ticket content."""
    t0 = time.time()
    trace_args = {
        "subject_chars": len(subject or ""),
        "body_chars": len(body),
        "channel": channel,
        "category": category,
        "priority": priority,
    }

    subject_safe = neutralize_delimiter(subject or "", "</ticket>")
    body_safe = neutralize_delimiter(body, "</ticket>")
    ticket_payload = (
        f"<ticket>\nChannel: {channel}\nCategory: {category}\nPriority: {priority}\n"
        f"Subject: {subject_safe}\nBody:\n{body_safe}\n</ticket>"
    )

    system_prompt = build_drafting_system_prompt(policy_text)
    messages = [LLMMessage(role="user", content=ticket_payload)]

    try:
        response = provider.generate(
            system=system_prompt,
            messages=messages,
            tools=None,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
        )
        if response.truncated:
            raise LLMOutputTruncated("Drafting response truncated by token limit.")

        raw_text = _strip_code_fences(response.text)
        try:
            data = json.loads(raw_text)
            parsed = DraftOutput.model_validate(data)
        except Exception as exc:
            if isinstance(exc, ValidationError):
                _log_validation_error("Draft", exc)
            # One repair attempt
            logger.info("Draft output invalid JSON; attempting single repair")
            repair_messages = list(messages) + [
                LLMMessage(role="assistant", content=response.text),
                LLMMessage(role="user", content=DRAFTING_REPAIR_PROMPT),
            ]
            repair_resp = provider.generate(
                system=system_prompt,
                messages=repair_messages,
                tools=None,
                max_output_tokens=max_output_tokens,
                temperature=0.0,
            )
            if repair_resp.truncated:
                raise LLMOutputTruncated("Drafting repair response truncated.")
            repaired_text = _strip_code_fences(repair_resp.text)
            try:
                repaired_data = json.loads(repaired_text)
                parsed = DraftOutput.model_validate(repaired_data)
            except ValidationError as val_exc:
                _log_validation_error("Draft repair", val_exc)
                raise

        # Post-processing flags on draft reply
        flags: list[ReviewFlag] = []
        reply = parsed.reply_text

        # 1. Unknown placeholder flag
        placeholders_in_reply = PLACEHOLDER_PATTERN.findall(reply)
        for ph in placeholders_in_reply:
            if ph not in ALLOWED_PLACEHOLDERS:
                flags.append(
                    ReviewFlag(
                        code="unknown_placeholder",
                        message=f"Placeholder '{ph}' is not in the allowed placeholder vocabulary.",
                        where="draft_reply",
                    )
                )

        # 2. Number not in policy or ticket (excluding placeholders)
        reply_no_placeholders = PLACEHOLDER_PATTERN.sub(" ", reply)
        numbers_in_reply = re.findall(r"\b\d+\b", reply_no_placeholders)
        combined_source = f"{policy_text}\n{body}\n{subject or ''}"
        for num in numbers_in_reply:
            if not re.search(r"\b" + re.escape(num) + r"\b", combined_source):
                flags.append(
                    ReviewFlag(
                        code="number_not_in_policy_or_ticket",
                        message=f"Figure '{num}' appears in draft reply but is absent from policies and ticket.",
                        where="draft_reply",
                    )
                )

        # 3. Identifier not in ticket
        identifiers_in_reply = IDENTIFIER_PATTERN.findall(reply)
        combined_ticket = f"{body}\n{subject or ''}"
        for ident in identifiers_in_reply:
            if not re.search(r"\b" + re.escape(ident) + r"\b", combined_ticket, re.IGNORECASE):
                flags.append(
                    ReviewFlag(
                        code="identifier_not_in_ticket",
                        message=f"Identifier '{ident}' appears in draft reply but was not in the ticket.",
                        where="draft_reply",
                    )
                )

        # 4. Overpromise wording
        reply_lower = reply.lower()
        for word in OVERPROMISE_WORDS:
            if re.search(r"\b" + re.escape(word) + r"\b", reply_lower):
                flags.append(
                    ReviewFlag(
                        code="overpromise_wording",
                        message=f"Draft reply contains unconditional commitment word '{word}'.",
                        where="draft_reply",
                    )
                )

        # 5. Unknown policy ref
        valid_headings = set(extract_policy_headings(policy_text))
        for ref in parsed.policy_refs:
            if ref not in valid_headings:
                flags.append(
                    ReviewFlag(
                        code="unknown_policy_ref",
                        message=f"Policy reference '{ref}' is not an exact section heading in policies.md.",
                        where="policy_refs",
                    )
                )

        # 6. Contact detail not in policy
        emails = EMAIL_PATTERN.findall(reply)
        for em in emails:
            if em.lower() not in policy_text.lower():
                flags.append(
                    ReviewFlag(
                        code="contact_detail_not_in_policy",
                        message=f"Email '{em}' in reply is not found in policy document.",
                        where="draft_reply",
                    )
                )
        urls = URL_PATTERN.findall(reply)
        for u in urls:
            if u.lower() not in policy_text.lower():
                flags.append(
                    ReviewFlag(
                        code="contact_detail_not_in_policy",
                        message=f"URL '{u}' in reply is not found in policy document.",
                        where="draft_reply",
                    )
                )
        phones = PHONE_PATTERN.findall(reply)
        for ph in phones:
            if ph not in policy_text:
                flags.append(
                    ReviewFlag(
                        code="contact_detail_not_in_policy",
                        message=f"Phone number '{ph}' in reply is not found in policy document.",
                        where="draft_reply",
                    )
                )

        dur_ms = int(round((time.time() - t0) * 1000))
        result = ToolResult(
            call_id=call_id,
            tool="draft_ticket_response",
            args=trace_args,
            ok=True,
            data={
                "reply_chars": len(parsed.reply_text),
                "policy_refs_count": len(parsed.policy_refs),
                "flags_count": len(flags),
            },
            error=None,
            duration_ms=dur_ms,
        )
        usage = {
            "prompt_tokens": getattr(response.usage, "input_tokens", 0) if response.usage else 0,
            "completion_tokens": getattr(response.usage, "output_tokens", 0) if response.usage else 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
        }
        return result, parsed, flags, usage

    except Exception as exc:
        dur_ms = int(round((time.time() - t0) * 1000))
        err_msg = str(exc)
        code = getattr(exc, "code", "drafting_failed")
        result = ToolResult(
            call_id=call_id,
            tool="draft_ticket_response",
            args=trace_args,
            ok=False,
            error=ToolError(code=code, message=err_msg),
            duration_ms=dur_ms,
        )
        return result, None, [], {}


def tool_create_triage_proposal(
    call_id: str,
    *,
    db: Session,
    engagement_id: int,
    subject: str | None,
    body: str,
    channel: str,
    category: str,
    secondary_category: str | None,
    priority: str,
    queue: str,
    escalation: bool,
    rule_id: str | None,
    rule_definition: str | None,
    signals: list[dict[str, Any]],
    rationale: str | None,
    draft_reply: str,
    policy_refs: list[str],
    reviewer_note: str | None,
    flags: list[dict[str, Any]],
    tool_trace: list[dict[str, Any]],
    model: str | None,
    usage: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> tuple[ToolResult, TriageProposal]:
    """Persist the generated proposal in the database with status awaiting_approval."""
    t0 = time.time()
    ticket_hash = compute_ticket_hash(subject=subject, body=body, channel=channel)

    trace_args = {
        "engagement_id": engagement_id,
        "category": category,
        "priority": priority,
        "queue": queue,
        "flags_count": len(flags),
    }

    proposal = TriageProposal(
        engagement_id=engagement_id,
        ticket_hash=ticket_hash,
        subject=subject,
        ticket_text=body,
        channel=channel,
        proposed_category=category,
        secondary_category=secondary_category,
        proposed_priority=priority,
        proposed_queue=queue,
        escalation=escalation,
        rule_fired=rule_id,
        reasoning=rule_definition or "",
        rationale=rationale or "",
        signals=signals,
        flags=flags,
        tool_trace=tool_trace,
        draft_reply=draft_reply,
        policy_refs=policy_refs,
        reviewer_note=reviewer_note,
        model=model,
        usage=usage,
        error=error,
        status=ProposalStatus.awaiting_approval,
    )
    db.add(proposal)
    db.flush()

    dur_ms = int(round((time.time() - t0) * 1000))
    result = ToolResult(
        call_id=call_id,
        tool="create_triage_proposal",
        args=trace_args,
        ok=True,
        data={
            "proposal_id": proposal.id,
            "ticket_hash": ticket_hash,
            "status": proposal.status.value if hasattr(proposal.status, "value") else str(proposal.status),
        },
        error=None,
        duration_ms=dur_ms,
    )
    return result, proposal
