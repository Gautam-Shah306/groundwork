"""Background runner for Evaluation Benchmark runs (B5).

Orchestrates sequential ticket processing with pacing, rate-limit backoff,
stop/resume events, item persistence, and comprehensive scoring.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.evaluation.dataset import EvalTicket, load_eval_tickets, select_sample
from app.evaluation.metrics import compute_evaluation_metrics
from app.llm.base import LLMProvider
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMModelNotFound,
    LLMQuotaExhausted,
    LLMRateLimited,
    scrub_secrets,
)
from app.llm.factory import get_provider
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


def clear_stop_event(run_id: int) -> None:
    with _RUN_STOP_LOCK:
        _RUN_STOP_EVENTS.pop(run_id, None)


def mark_interrupted_eval_runs_paused(session: Session) -> int:
    """Mark all EvalRun rows with status=running as paused (code=interrupted) on startup."""
    running_runs = session.scalars(
        select(EvalRun).where(EvalRun.status == EvalRunStatus.running)
    ).all()
    count = 0
    for r in running_runs:
        r.status = EvalRunStatus.paused
        r.error = {
            "code": "interrupted",
            "message": "Evaluation run was interrupted by server restart.",
        }
        count += 1
    if count:
        session.commit()
        logger.info("Marked %s interrupted evaluation runs as paused.", count)
    return count


class EvaluationRunner:
    """Orchestrates an evaluation run over a sample of eval tickets."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        run_id: int,
        settings: Settings,
        eval_tickets_path: str = "data/eval_tickets.json",
        config: TriageConfig | None = None,
        provider: LLMProvider | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session_factory = session_factory
        self.run_id = run_id
        self.settings = settings
        self.eval_tickets_path = eval_tickets_path
        self.config = config
        self._provider = provider
        self.sleep = sleep_fn
        self.stop_event = get_stop_event(run_id)

    def run(self) -> None:
        """Entry point for execution thread."""
        try:
            self._execute()
        except Exception as exc:
            logger.exception("EvaluationRunner unhandled exception in run %s: %s", self.run_id, exc)
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

        first_in_session = True

        # Phase 1: Classification phase
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
                    # Terminal error: pause run gracefully without recording failure on current ticket
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

            # Persist item result (classification only)
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
                    # draft will be evaluated in Phase 2 if sampled
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
                    all_run_items = session.scalars(
                        select(EvalItem).where(EvalItem.run_id == self.run_id)
                    ).all()
                    run_obj.progress_done = len(all_run_items)
                    run_obj.progress_total = total_sample
                session.commit()

        # Check for cancellation before Phase 2
        if self.stop_event.is_set():
            with self.session_factory() as session:
                run_obj = session.get(EvalRun, self.run_id)
                if run_obj:
                    run_obj.status = EvalRunStatus.cancelled
                    session.commit()
            return

        # Phase 2: Draft phase (A5: runs AFTER classification phase over deterministic stratified sample of completed items)
        if drafts_sample > 0:
            policy_text = load_policies_text()
            with self.session_factory() as session:
                completed_items = session.scalars(
                    select(EvalItem).where(
                        EvalItem.run_id == self.run_id,
                        EvalItem.status == "success",
                    )
                ).all()

            completed_item_ids = {it.ticket_id for it in completed_items}
            completed_sample_tickets = [t for t in sample_tickets if t.id in completed_item_ids]

            # Select deterministic stratified sample of size min(drafts_sample, len(completed_sample_tickets))
            k_drafts = min(drafts_sample, len(completed_sample_tickets))
            draft_sample_tickets = select_sample(completed_sample_tickets, k_drafts)
            draft_ticket_ids = {t.id for t in draft_sample_tickets}

            for draft_ticket in draft_sample_tickets:
                if self.stop_event.is_set():
                    break

                with self.session_factory() as session:
                    it_obj = session.scalar(
                        select(EvalItem).where(
                            EvalItem.run_id == self.run_id,
                            EvalItem.ticket_id == draft_ticket.id,
                        )
                    )
                    if it_obj is None or it_obj.draft is not None:
                        continue

                    # Pacing wait
                    if pacing_seconds > 0:
                        self.sleep(float(pacing_seconds))

                    draft_data: dict[str, Any] | None = None
                    d_usage: dict[str, Any] = {}
                    try:
                        res_d, draft_out, draft_flags, draft_usage = tool_draft_ticket_response(
                            "d1",
                            subject=draft_ticket.subject,
                            body=draft_ticket.body,
                            channel=draft_ticket.channel,
                            category=it_obj.predicted_category or "product_questions",
                            priority=it_obj.predicted_priority or "low",
                            policy_text=policy_text,
                            provider=provider,
                            max_output_tokens=self.settings.llm_triage_max_output_tokens,
                            escalation=it_obj.escalation,
                            rule_id=it_obj.rule_id,
                        )
                        d_usage = draft_usage or {}
                        if draft_out is not None:
                            # STORE FLAGS ONLY - NEVER the reply text! (A5 / R3 / Secret hygiene)
                            draft_data = {
                                "flags": [f.model_dump(mode="json") if hasattr(f, "model_dump") else f for f in draft_flags],
                                "reply_chars": len(draft_out.reply_text) if draft_out.reply_text else 0,
                                "policy_refs_valid": bool(draft_out.policy_refs),
                                "draft_unavailable": False,
                                "error_code": None,
                            }
                        else:
                            draft_data = {
                                "flags": [{"code": "draft_unavailable", "message": "Draft output unavailable."}],
                                "reply_chars": 0,
                                "policy_refs_valid": False,
                                "draft_unavailable": True,
                                "error_code": "draft_failed",
                            }
                    except Exception as d_exc:
                        logger.warning("Drafting failed on ticket %s: %s", draft_ticket.id, d_exc)
                        draft_data = {
                            "flags": [{"code": "draft_error", "message": str(d_exc)}],
                            "reply_chars": 0,
                            "policy_refs_valid": False,
                            "draft_unavailable": True,
                            "error_code": d_exc.__class__.__name__,
                        }

                    it_obj.draft = draft_data
                    it_obj.provider_calls += 1
                    if d_usage and it_obj.usage:
                        curr_u = dict(it_obj.usage)
                        curr_u["prompt_tokens"] = (curr_u.get("prompt_tokens") or 0) + (d_usage.get("prompt_tokens") or 0)
                        curr_u["completion_tokens"] = (curr_u.get("completion_tokens") or 0) + (d_usage.get("completion_tokens") or 0)
                        curr_u["total_tokens"] = (curr_u.get("total_tokens") or 0) + (d_usage.get("total_tokens") or 0)
                        it_obj.usage = curr_u
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
