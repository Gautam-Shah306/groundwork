"""Background execution runner for evaluation benchmark runs (B5).

Handles pacing, rate-limit backoff, terminal error pauses, checkpointing, and resumption.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.evaluation.dataset import EvalTicket, load_eval_tickets, select_sample
from app.evaluation.metrics import compute_evaluation_metrics
from app.llm import get_provider
from app.llm.base import LLMProvider
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMModelNotFound,
    LLMQuotaExhausted,
    LLMRateLimited,
    scrub_secrets,
)
from app.models import EvalItem, EvalRun, EvalRunStatus, utc_now
from app.triage.config import TriageConfig, load_triage_config
from app.triage.prompts import load_policies_text
from app.triage.service import TriageTicketInput, classify_and_prioritise
from app.triage.tools import tool_draft_ticket_response

logger = logging.getLogger(__name__)

# Registry of active stop events per run_id
_RUN_STOP_EVENTS: dict[int, threading.Event] = {}
_RUN_STOP_LOCK = threading.Lock()


def get_stop_event(run_id: int) -> threading.Event:
    with _RUN_STOP_LOCK:
        if run_id not in _RUN_STOP_EVENTS:
            _RUN_STOP_EVENTS[run_id] = threading.Event()
        return _RUN_STOP_EVENTS[run_id]


def reset_stop_event(run_id: int) -> threading.Event:
    with _RUN_STOP_LOCK:
        ev = threading.Event()
        _RUN_STOP_EVENTS[run_id] = ev
        return ev


def clear_stop_event(run_id: int) -> None:
    with _RUN_STOP_LOCK:
        _RUN_STOP_EVENTS.pop(run_id, None)


def mark_interrupted_eval_runs_paused(session: Session) -> int:
    """Startup hook: mark any running EvalRun as paused with interrupted status."""
    stale_runs = session.scalars(
        select(EvalRun).where(EvalRun.status == EvalRunStatus.running)
    ).all()
    count = 0
    for r in stale_runs:
        r.status = EvalRunStatus.paused
        r.error = {
            "code": "interrupted",
            "message": "Run interrupted by server restart. Can be resumed.",
        }
        count += 1
    if count > 0:
        session.commit()
    return count


class EvaluationRunner:
    """Runs an evaluation benchmark in a background thread."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        run_id: int,
        settings: Settings,
        *,
        provider: LLMProvider | None = None,
        config: TriageConfig | None = None,
        eval_tickets_path: str = "data/eval_tickets.json",
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session_factory = session_factory
        self.run_id = run_id
        self.settings = settings
        self._provider = provider
        self.config = config
        self.eval_tickets_path = eval_tickets_path
        self.sleep = sleep_fn
        self.stop_event = reset_stop_event(run_id)

    def run(self) -> None:
        """Execute the evaluation run."""
        try:
            self._execute()
        except Exception as exc:
            logger.exception("Unexpected error in EvaluationRunner for run %s", self.run_id)
            with self.session_factory() as session:
                run_obj = session.get(EvalRun, self.run_id)
                if run_obj and run_obj.status == EvalRunStatus.running:
                    run_obj.status = EvalRunStatus.failed
                    run_obj.error = {
                        "code": "unexpected_runner_error",
                        "message": scrub_secrets(str(exc), secrets=(self.settings.llm_api_key,)),
                    }
                    session.commit()
        finally:
            clear_stop_event(self.run_id)

    def _execute(self) -> None:
        # 1. Load run metadata
        with self.session_factory() as session:
            run_obj = session.get(EvalRun, self.run_id)
            if not run_obj:
                logger.error("EvalRun %s not found.", self.run_id)
                return
            if run_obj.status in (EvalRunStatus.cancelled, EvalRunStatus.completed):
                return

            sample_size = run_obj.sample_size
            drafts_sample = int(run_obj.config.get("drafts_sample", 0)) if run_obj.config else 0
            model_name = run_obj.model

        # 2. Resolve provider and configuration
        provider = self._provider
        if provider is None:
            provider = get_provider(self.settings)

        triage_config = self.config if self.config is not None else load_triage_config()

        # 3. Load test set and select sample
        all_tickets = load_eval_tickets(self.eval_tickets_path, config=triage_config)
        sample_tickets = select_sample(all_tickets, sample_size)
        total_sample = len(sample_tickets)

        # 4. Check existing successful items for resume support
        with self.session_factory() as session:
            existing_items = session.scalars(
                select(EvalItem).where(EvalItem.run_id == self.run_id)
            ).all()
            completed_ticket_ids = {it.ticket_id for it in existing_items if it.status == "success"}

            run_obj = session.get(EvalRun, self.run_id)
            if run_obj:
                run_obj.progress_total = total_sample
                run_obj.progress_done = len(completed_ticket_ids)
                session.commit()

        tickets_to_run = [t for t in sample_tickets if t.id not in completed_ticket_ids]
        pacing_seconds = getattr(self.settings, "eval_pacing_seconds", 2)
        max_rate_limit_waits = getattr(self.settings, "eval_max_rate_limit_waits", 3)
        max_wait_seconds = getattr(self.settings, "eval_max_wait_seconds", 120)

        # Pre-load policy text if drafting is enabled
        policy_text = ""
        if drafts_sample > 0:
            policy_text = load_policies_text()

        first_in_session = True

        # 5. Process each ticket
        for ticket in tickets_to_run:
            # Check for cancellation
            if self.stop_event.is_set():
                with self.session_factory() as session:
                    run_obj = session.get(EvalRun, self.run_id)
                    if run_obj:
                        run_obj.status = EvalRunStatus.cancelled
                        session.commit()
                return

            with self.session_factory() as session:
                run_obj = session.get(EvalRun, self.run_id)
                if run_obj and run_obj.status == EvalRunStatus.cancelled:
                    return

            # Pacing wait
            if not first_in_session and pacing_seconds > 0:
                self.sleep(float(pacing_seconds))
            first_in_session = False

            # Rate-limit retry loop
            rl_wait_count = 0
            backoff_delay = 10.0
            item_success = False
            item_error_code: str | None = None
            res_cp = None

            while True:
                try:
                    res_cp = classify_and_prioritise(
                        TriageTicketInput(
                            subject=ticket.subject,
                            body=ticket.body,
                            channel=ticket.channel,
                        ),
                        provider=provider,
                        settings=self.settings,
                        config=triage_config,
                        call_id_prefix="c",
                        max_output_tokens=self.settings.llm_triage_max_output_tokens,
                    )
                    if res_cp.error is not None:
                        item_error_code = res_cp.error.get("code", "classification_failed")
                    else:
                        item_success = True
                    break

                except LLMRateLimited as rle:
                    rl_wait_count += 1
                    if rl_wait_count > max_rate_limit_waits:
                        logger.warning("Ticket %s exceeded max rate-limit waits (%s).", ticket.id, max_rate_limit_waits)
                        item_error_code = "rate_limit"
                        break
                    wait_time = rle.retry_after_seconds if rle.retry_after_seconds is not None else backoff_delay
                    wait_time = min(wait_time, max_wait_seconds)
                    logger.info("Rate limit hit on ticket %s. Waiting %s seconds (attempt %s).", ticket.id, wait_time, rl_wait_count)
                    self.sleep(wait_time)
                    backoff_delay = min(backoff_delay * 2, max_wait_seconds)

                except (LLMQuotaExhausted, LLMAuthError, LLMModelNotFound) as term_exc:
                    # Terminal error: pause run gracefully
                    scrubbed = scrub_secrets(str(term_exc), secrets=(self.settings.llm_api_key,))
                    logger.error("Terminal LLM error during eval run %s: %s", self.run_id, scrubbed)
                    with self.session_factory() as session:
                        run_obj = session.get(EvalRun, self.run_id)
                        if run_obj:
                            run_obj.status = EvalRunStatus.paused
                            run_obj.error = {"code": term_exc.code, "message": scrubbed}
                            session.commit()
                    return

                except Exception as exc:
                    logger.exception("Unexpected failure on ticket %s", ticket.id)
                    item_error_code = exc.__class__.__name__
                    break

            # Check if optional draft check applies (first drafts_sample tickets in sample_tickets)
            draft_data: dict[str, Any] | None = None
            ticket_sample_index = next(
                (i for i, st in enumerate(sample_tickets) if st.id == ticket.id),
                999999,
            )
            if item_success and res_cp is not None and ticket_sample_index < drafts_sample:
                try:
                    res_d, draft_out, draft_flags, draft_usage = tool_draft_ticket_response(
                        "d1",
                        subject=ticket.subject,
                        body=ticket.body,
                        channel=ticket.channel,
                        category=res_cp.category or "product_questions",
                        priority=res_cp.priority or "low",
                        policy_text=policy_text,
                        provider=provider,
                        max_output_tokens=self.settings.llm_triage_max_output_tokens,
                        escalation=res_cp.escalation,
                        rule_id=res_cp.rule_id,
                    )
                    if draft_out is not None:
                        draft_data = {
                            "reply": draft_out.reply_text,
                            "flags": [f.model_dump(mode="json") for f in draft_flags],
                            "reviewer_note": draft_out.reviewer_note,
                            "policy_refs": draft_out.policy_refs,
                        }
                    else:
                        draft_data = {
                            "reply": "",
                            "flags": [{"code": "draft_unavailable", "message": "Draft output unavailable."}],
                            "reviewer_note": None,
                            "policy_refs": [],
                        }
                except Exception as d_exc:
                    logger.warning("Drafting failed on ticket %s: %s", ticket.id, d_exc)
                    draft_data = {
                        "reply": "",
                        "flags": [{"code": "draft_unavailable", "message": str(d_exc)}],
                        "reviewer_note": None,
                        "policy_refs": [],
                    }

            # Persist item result
            with self.session_factory() as session:
                existing_item = session.scalar(
                    select(EvalItem).where(
                        EvalItem.run_id == self.run_id,
                        EvalItem.ticket_id == ticket.id,
                    )
                )

                if existing_item is None:
                    existing_item = EvalItem(run_id=self.run_id, ticket_id=ticket.id)
                    session.add(existing_item)

                if item_success and res_cp is not None:
                    existing_item.status = "success"
                    existing_item.error_code = None
                    existing_item.predicted_category = res_cp.category
                    existing_item.predicted_secondary = res_cp.secondary
                    existing_item.predicted_signals = [
                        s.get("signal", s) if isinstance(s, dict) else s for s in res_cp.signals
                    ]
                    existing_item.flags = res_cp.flags
                    existing_item.predicted_priority = res_cp.priority
                    existing_item.rule_id = res_cp.rule_id
                    existing_item.predicted_queue = res_cp.queue
                    existing_item.escalation = res_cp.escalation
                    existing_item.usage = res_cp.usage
                    existing_item.duration_ms = res_cp.duration_ms
                    existing_item.provider_calls = res_cp.provider_calls
                    existing_item.draft = draft_data
                else:
                    existing_item.status = "error"
                    existing_item.error_code = item_error_code or "item_failed"
                    existing_item.predicted_category = None
                    existing_item.predicted_secondary = None
                    existing_item.predicted_signals = []
                    existing_item.flags = []
                    existing_item.predicted_priority = None
                    existing_item.rule_id = None
                    existing_item.predicted_queue = None
                    existing_item.escalation = False
                    existing_item.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    existing_item.duration_ms = 0
                    existing_item.provider_calls = 1
                    existing_item.draft = None

                # Update run progress
                run_obj = session.get(EvalRun, self.run_id)
                if run_obj:
                    # Count completed items
                    all_run_items = session.scalars(
                        select(EvalItem).where(EvalItem.run_id == self.run_id)
                    ).all()
                    run_obj.progress_done = len(all_run_items)
                    run_obj.progress_total = total_sample
                session.commit()

        # 6. Post-processing: check if all items finished
        with self.session_factory() as session:
            run_obj = session.get(EvalRun, self.run_id)
            if not run_obj or run_obj.status == EvalRunStatus.cancelled:
                return

            all_items = session.scalars(
                select(EvalItem).where(EvalItem.run_id == self.run_id)
            ).all()

            if len(all_items) >= total_sample:
                # Compute comprehensive metrics
                metrics = compute_evaluation_metrics(
                    all_items,
                    sample_tickets,
                    draft_flags_checked=drafts_sample,
                    config=triage_config,
                )

                # Total usage
                total_prompt = sum(it.usage.get("prompt_tokens", 0) for it in all_items if it.usage)
                total_comp = sum(it.usage.get("completion_tokens", 0) for it in all_items if it.usage)
                total_tokens = sum(it.usage.get("total_tokens", 0) for it in all_items if it.usage)
                total_calls = sum(it.provider_calls for it in all_items)

                run_obj.status = EvalRunStatus.completed
                run_obj.results = metrics
                run_obj.usage = {
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_comp,
                    "total_tokens": total_tokens,
                    "provider_calls": total_calls,
                    "estimated_cost_usd": None,
                }
                run_obj.progress_done = total_sample
                run_obj.finished_at = utc_now()
                session.commit()
