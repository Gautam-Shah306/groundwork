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
from app.triage.service import TriageTicketInput, classify_and_prioritise
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
    # Step 1 & 2: classify_and_prioritise (c1, c2) - Shared triage logic
    # -------------------------------------------------------------
    if _timed_out():
        raise LLMTimeout("Triage pipeline timed out before classification.")

    ticket_in = TriageTicketInput(subject=subject, body=body, channel=channel)
    res_cp = classify_and_prioritise(
        ticket_in,
        provider=provider,
        config=triage_config,
        call_id_prefix="c",
        max_output_tokens=max_output_tokens,
    )
    for t_res in res_cp.tool_trace:
        tool_trace.append(t_res)
    _add_usage(res_cp.usage)

    if res_cp.error is not None or res_cp.category is None:
        err_msg = res_cp.error.get("message", "Classification failed.") if res_cp.error else "Classification failed."
        err_code = res_cp.error.get("code", "classification_failed") if res_cp.error else "classification_failed"
        if err_code == "llm_output_truncated":
            raise LLMOutputTruncated(err_msg)
        raise ValueError(f"Classification failed: {err_msg}")

    combined_flags.extend(res_cp.flags)
    category = res_cp.category
    secondary_category = res_cp.secondary
    serialized_signals = res_cp.signals
    priority_val = str(res_cp.priority)
    rule_id = res_cp.rule_id
    rule_definition = res_cp.rule_definition
    rationale = res_cp.rationale
    queue = res_cp.queue
    escalation = res_cp.escalation

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
                category=category,
                priority=priority_val,
                policy_text=policy_text,
                provider=provider,
                max_output_tokens=max_output_tokens,
                escalation=escalation,
                rule_id=rule_id,
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
        category=category,
        secondary_category=secondary_category,
        priority=priority_val,
        queue=queue,
        escalation=escalation,
        rule_id=rule_id,
        rule_definition=rule_definition,
        signals=serialized_signals,
        rationale=rationale,
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
