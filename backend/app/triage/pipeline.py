"""Execution pipeline for Support Triage automation.

Fixed four-step order:
  c1: classify_ticket (LLM: temperature=0, no tools offered)
  c2: recommend_priority (Deterministic Python: evaluate_priority on signals, queue from queues.yaml)
  c3: draft_ticket_response (LLM: temperature=0, no tools offered)
  c4: create_triage_proposal (Database write, status awaiting_approval)

Non-negotiable rules:
- Priority and queue are NEVER taken from model output (R1, R4).
- Overall pipeline timeout: 90 seconds.
- Classification failure is fatal (no proposal created).
- Drafting failure is non-fatal (proposal created with empty draft, flag draft_unavailable).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.agent.tools import ToolResult
from app.llm.base import LLMProvider
from app.llm.errors import LLMError, LLMOutputTruncated, LLMTimeout
from app.models import TriageProposal
from app.triage.config import TriageConfig, load_triage_config
from app.triage.prompts import load_policies_text
from app.triage.tools import (
    tool_classify_ticket,
    tool_create_triage_proposal,
    tool_draft_ticket_response,
    tool_recommend_priority,
)

logger = logging.getLogger(__name__)

PIPELINE_TIMEOUT_SECONDS: float = 90.0


def run_triage_pipeline(
    *,
    db: Session,
    engagement_id: int,
    subject: str | None,
    body: str,
    channel: str,
    provider: LLMProvider,
    config: TriageConfig | None = None,
    max_output_tokens: int | None = None,
    timeout_seconds: float = PIPELINE_TIMEOUT_SECONDS,
) -> tuple[TriageProposal, list[ToolResult]]:
    """Execute the Support Triage pipeline in fixed sequential order."""
    t0 = time.time()
    triage_config = config if config is not None else load_triage_config()
    tool_trace: list[ToolResult] = []
    combined_flags: list[dict[str, Any]] = []
    accumulated_usage: dict[str, int] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    def _timed_out() -> bool:
        return (time.time() - t0) >= timeout_seconds

    def _add_usage(u: dict[str, Any]) -> None:
        if u:
            accumulated_usage["prompt_tokens"] += u.get("prompt_tokens") or 0
            accumulated_usage["completion_tokens"] += u.get("completion_tokens") or 0
            accumulated_usage["total_tokens"] += u.get("total_tokens") or 0

    # -------------------------------------------------------------
    # Step 1: classify_ticket (c1) - FATAL on failure
    # -------------------------------------------------------------
    if _timed_out():
        raise LLMTimeout("Triage pipeline timed out before classification.")

    res_c1, classification_out, flags_c1, usage_c1 = tool_classify_ticket(
        "c1",
        subject=subject,
        body=body,
        channel=channel,
        provider=provider,
        config=triage_config,
        max_output_tokens=max_output_tokens,
    )
    tool_trace.append(res_c1)
    _add_usage(usage_c1)

    if not res_c1.ok or classification_out is None:
        err_msg = res_c1.error.message if res_c1.error else "Classification failed."
        err_code = res_c1.error.code if res_c1.error else "classification_failed"
        if err_code == "llm_output_truncated":
            raise LLMOutputTruncated(err_msg)
        raise ValueError(f"Classification failed: {err_msg}")

    for f in flags_c1:
        combined_flags.append(f.model_dump(mode="json"))

    extracted_signals = [s.signal for s in classification_out.signals]
    serialized_signals = [s.model_dump(mode="json") for s in classification_out.signals]

    # -------------------------------------------------------------
    # Step 2: recommend_priority (c2) - DETERMINISTIC
    # -------------------------------------------------------------
    if _timed_out():
        raise LLMTimeout("Triage pipeline timed out before priority evaluation.")

    res_c2, priority_decision, rule_definition, queue, escalation = tool_recommend_priority(
        "c2",
        signals=extracted_signals,
        category=classification_out.category,
        config=triage_config,
    )
    tool_trace.append(res_c2)

    priority_val = str(priority_decision.priority.value if hasattr(priority_decision.priority, "value") else priority_decision.priority)

    # -------------------------------------------------------------
    # Step 3: draft_ticket_response (c3) - NON-FATAL
    # -------------------------------------------------------------
    draft_reply = ""
    policy_refs: list[str] = []
    reviewer_note: str | None = None
    draft_error: dict[str, Any] | None = None

    if _timed_out():
        combined_flags.append({
            "code": "draft_unavailable",
            "message": "Drafting step timed out before execution.",
            "where": "draft_reply",
        })
        draft_error = {"code": "timeout", "message": "Drafting timed out."}
    else:
        try:
            policy_text = load_policies_text()
            res_c3, draft_out, flags_c3, usage_c3 = tool_draft_ticket_response(
                "c3",
                subject=subject,
                body=body,
                channel=channel,
                category=classification_out.category,
                priority=priority_val,
                policy_text=policy_text,
                provider=provider,
                max_output_tokens=max_output_tokens,
            )
            tool_trace.append(res_c3)
            _add_usage(usage_c3)

            if res_c3.ok and draft_out:
                draft_reply = draft_out.reply_text
                policy_refs = draft_out.policy_refs
                reviewer_note = draft_out.reviewer_note
                for f in flags_c3:
                    combined_flags.append(f.model_dump(mode="json"))
            else:
                combined_flags.append({
                    "code": "draft_unavailable",
                    "message": res_c3.error.message if res_c3.error else "Draft response could not be generated.",
                    "where": "draft_reply",
                })
                draft_error = res_c3.error.model_dump(mode="json") if res_c3.error else {"code": "draft_failed"}

        except Exception as exc:
            logger.warning("Draft response failed: %s", exc)
            combined_flags.append({
                "code": "draft_unavailable",
                "message": f"Draft generation error: {exc}",
                "where": "draft_reply",
            })
            draft_error = {"code": "draft_error", "message": str(exc)}

    # -------------------------------------------------------------
    # Step 4: create_triage_proposal (c4) - DB WRITE
    # -------------------------------------------------------------
    serialized_trace = [t.model_dump(mode="json") for t in tool_trace]

    res_c4, proposal = tool_create_triage_proposal(
        "c4",
        db=db,
        engagement_id=engagement_id,
        subject=subject,
        body=body,
        channel=channel,
        category=classification_out.category,
        secondary_category=classification_out.secondary_category,
        priority=priority_val,
        queue=queue,
        escalation=escalation,
        rule_id=priority_decision.rule_id,
        rule_definition=rule_definition,
        signals=serialized_signals,
        rationale=classification_out.rationale,
        draft_reply=draft_reply,
        policy_refs=policy_refs,
        reviewer_note=reviewer_note,
        flags=combined_flags,
        tool_trace=serialized_trace,
        model=provider.model_name or "",
        usage=accumulated_usage,
        error=draft_error,
    )
    tool_trace.append(res_c4)

    # Update proposal tool_trace to include c4 as well
    proposal.tool_trace = [t.model_dump(mode="json") for t in tool_trace]
    db.flush()

    return proposal, tool_trace
