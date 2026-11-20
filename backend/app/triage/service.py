"""Shared execution service for Support Triage classification and deterministic priority (B1).

Called by both the production triage API and the evaluation runner.
Strictly decoupled from evaluation labels and eval datasets.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools import ToolResult
from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.errors import LLMOutputTruncated
from app.triage.config import TriageConfig, load_triage_config
from app.triage.tools import tool_classify_ticket, tool_recommend_priority


class TriageTicketInput(BaseModel):
    """Input ticket for triage classification."""

    subject: str | None = None
    body: str
    channel: str = "chat"


class ClassificationAndPriorityResult(BaseModel):
    """Unified result of classification, post-processing, and deterministic priority."""

    category: str | None = None
    secondary: str | None = None
    signals: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
    rule_id: str | None = None
    rule_definition: str | None = None
    priority: str | None = None
    queue: str | None = None
    escalation: bool = False
    rationale: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    duration_ms: int = 0
    provider_calls: int = 0
    tool_trace: list[ToolResult] = Field(default_factory=list)


def classify_and_prioritise(
    ticket: TriageTicketInput | dict[str, Any],
    provider: LLMProvider,
    settings: Settings | None = None,
    config: TriageConfig | None = None,
    *,
    call_id_prefix: str = "c",
    max_output_tokens: int | None = None,
) -> ClassificationAndPriorityResult:
    """Execute classification, quote verification, post-processing flags, and deterministic priority.

    Used by both production triage proposals and the evaluation benchmark runner.
    """
    t0 = time.time()
    triage_config = config if config is not None else load_triage_config()

    if isinstance(ticket, dict):
        ticket_obj = TriageTicketInput(**ticket)
    else:
        ticket_obj = ticket

    resolved_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else (settings.llm_triage_max_output_tokens if settings else 2000)
    )

    # 1. Classification (c1)
    res_c1, classification_out, flags_c1, usage_c1 = tool_classify_ticket(
        f"{call_id_prefix}1",
        subject=ticket_obj.subject,
        body=ticket_obj.body,
        channel=ticket_obj.channel,
        provider=provider,
        config=triage_config,
        max_output_tokens=resolved_tokens,
    )

    combined_flags = [f.model_dump(mode="json") for f in flags_c1]
    accumulated_usage = {
        "prompt_tokens": (usage_c1.get("prompt_tokens") or 0) if usage_c1 else 0,
        "completion_tokens": (usage_c1.get("completion_tokens") or 0) if usage_c1 else 0,
        "total_tokens": (usage_c1.get("total_tokens") or 0) if usage_c1 else 0,
    }

    if not res_c1.ok or classification_out is None:
        err_msg = res_c1.error.message if res_c1.error else "Classification failed."
        err_code = res_c1.error.code if res_c1.error else "classification_failed"
        return ClassificationAndPriorityResult(
            flags=combined_flags,
            usage=accumulated_usage,
            error={"code": err_code, "message": err_msg},
            duration_ms=int(round((time.time() - t0) * 1000)),
            provider_calls=1,
            tool_trace=[res_c1],
        )

    # 2. Priority & Queue (c2) - DETERMINISTIC
    extracted_signals = [s.signal for s in classification_out.signals]
    serialized_signals = [
        {
            "signal": s.signal,
            "quote_verified": s.quote_verified if hasattr(s, "quote_verified") else True,
            "source_quote": s.source_quote,
        }
        for s in classification_out.signals
    ]

    res_c2, priority_decision, rule_definition, queue, escalation = tool_recommend_priority(
        f"{call_id_prefix}2",
        signals=extracted_signals,
        category=classification_out.category,
        config=triage_config,
    )

    priority_val = str(
        priority_decision.priority.value
        if hasattr(priority_decision.priority, "value")
        else priority_decision.priority
    )

    return ClassificationAndPriorityResult(
        category=classification_out.category,
        secondary=classification_out.secondary_category,
        signals=serialized_signals,
        flags=combined_flags,
        rule_id=priority_decision.rule_id,
        rule_definition=rule_definition,
        priority=priority_val,
        queue=queue,
        escalation=escalation,
        rationale=classification_out.rationale,
        usage=accumulated_usage,
        error=None,
        duration_ms=int(round((time.time() - t0) * 1000)),
        provider_calls=1,
        tool_trace=[res_c1, res_c2],
    )
