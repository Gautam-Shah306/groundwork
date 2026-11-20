"""Evaluation dataset loader and stratified sampler (B2).

Loads data/eval_tickets.json and validates schema and ground truth invariants.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_project_root
from app.triage.config import TriageConfig, load_triage_config
from app.triage.priority import evaluate_priority

TICKET_ID_REGEX = re.compile(r"^(?:EVAL|EV)-[0-9]{3}$")
VALID_CHANNELS = {"chat", "email", "web_form", "whatsapp"}
VALID_LANGUAGES = {"en", "hinglish"}


def _resolve_relative_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root if it does not exist locally."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        candidate = get_project_root() / p
        if candidate.exists():
            return candidate
    return p


class EvalTicket(BaseModel):
    """A labelled ticket in the evaluation test set with code-derived properties (A2)."""

    id: str
    subject: str | None = None
    body: str
    channel: str
    language: str
    true_category: str
    true_signals: list[str] = Field(default_factory=list)
    true_priority: str
    is_ambiguous: bool
    secondary_category: str | None = None
    true_queue: str = ""
    is_hinglish: bool = False
    is_short: bool = False


def compute_dataset_fingerprint(path: str | Path = "data/eval_tickets.json") -> str:
    """Compute SHA-256 hex digest of eval tickets file."""
    p = _resolve_relative_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Eval tickets file not found at {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compute_config_fingerprint(
    model: str,
    temperature: float = 0.0,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    dataset_path: str | Path = "data/eval_tickets.json",
    queues_path: str | Path = "config/queues.yaml",
    rules_path: str | Path = "config/priority_rules.yaml",
    policies_path: str | Path = "knowledge/policies.md",
) -> str:
    """Compute SHA-256 hex digest over all components defining the evaluation configuration."""
    from app.triage.prompts import (
        build_classification_system_prompt,
        build_drafting_system_prompt,
        load_policies_text,
    )

    hasher = hashlib.sha256()

    # 1. Classification system prompt text
    class_prompt = build_classification_system_prompt()
    hasher.update(class_prompt.encode("utf-8"))

    # 2. Draft system prompt text
    p_path = _resolve_relative_path(policies_path)
    policy_text = p_path.read_text(encoding="utf-8") if p_path.exists() else load_policies_text()
    draft_prompt = build_drafting_system_prompt(policy_text)
    hasher.update(draft_prompt.encode("utf-8"))

    # 3. Content of config/queues.yaml
    q_path = _resolve_relative_path(queues_path)
    if q_path.exists():
        hasher.update(q_path.read_bytes())

    # 4. Content of config/priority_rules.yaml
    r_path = _resolve_relative_path(rules_path)
    if r_path.exists():
        hasher.update(r_path.read_bytes())

    # 5. Dataset fingerprint
    ds_fp = compute_dataset_fingerprint(dataset_path)
    hasher.update(ds_fp.encode("utf-8"))

    # 6. Model name
    hasher.update(str(model).encode("utf-8"))

    # 7. Temperature
    hasher.update(str(temperature).encode("utf-8"))

    # 8. Reasoning effort
    hasher.update(str(reasoning_effort or "").encode("utf-8"))

    # 9. Max output tokens
    hasher.update(str(max_output_tokens or "").encode("utf-8"))

    return hasher.hexdigest()


def load_eval_tickets(
    path: str | Path = "data/eval_tickets.json",
    config: TriageConfig | None = None,
) -> list[EvalTicket]:
    """Load and validate all tickets from eval_tickets.json.

    Validates:
    - id matches (EVAL|EV)-[0-9]{3}
    - channel in valid channels
    - language in valid languages
    - true_category in config/queues.yaml
    - true_signals in config/priority_rules.yaml
    - true_priority matches deterministic evaluate_priority(true_signals).priority
    - is_ambiguous consistency with secondary_category
    - uniqueness of ticket IDs

    Derives in code (A2):
    - is_hinglish from language == "hinglish"
    - is_short from fewer than 12 words in body
    - true_queue from deterministic route_to_queue / evaluate_priority
    """
    p = _resolve_relative_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Eval tickets file not found at {p}")

    triage_config = config if config is not None else load_triage_config()
    known_categories = {c.id for c in triage_config.categories}
    known_signals = set(triage_config.signals.keys())

    with p.open("r", encoding="utf-8") as f:
        raw_items: list[dict[str, Any]] = json.load(f)

    seen_ids: set[str] = set()
    tickets: list[EvalTicket] = []

    for idx, item in enumerate(raw_items):
        tid = item.get("id")
        if not tid or not isinstance(tid, str) or not TICKET_ID_REGEX.match(tid):
            raise ValueError(f"Item {idx}: invalid id '{tid}'. Must match '(EVAL|EV)-[0-9]{{3}}'.")

        if tid in seen_ids:
            raise ValueError(f"Duplicate ticket id '{tid}' found at index {idx}.")
        seen_ids.add(tid)

        channel = item.get("channel")
        if channel not in VALID_CHANNELS:
            raise ValueError(f"Ticket {tid}: invalid channel '{channel}'. Allowed: {sorted(VALID_CHANNELS)}.")

        language = item.get("language")
        if language not in VALID_LANGUAGES:
            raise ValueError(f"Ticket {tid}: invalid language '{language}'. Allowed: {sorted(VALID_LANGUAGES)}.")

        true_cat = item.get("true_category")
        if true_cat not in known_categories:
            raise ValueError(f"Ticket {tid}: unknown true_category '{true_cat}'.")

        true_signals = item.get("true_signals") or []
        for s in true_signals:
            if s not in known_signals:
                raise ValueError(f"Ticket {tid}: unknown signal '{s}' in true_signals.")

        # Ground truth priority check
        expected_priority = evaluate_priority(true_signals, config=triage_config)
        expected_priority_val = (
            expected_priority.priority.value
            if hasattr(expected_priority.priority, "value")
            else str(expected_priority.priority)
        )
        actual_priority = item.get("true_priority")
        if actual_priority != expected_priority_val:
            raise ValueError(
                f"Ticket {tid}: true_priority '{actual_priority}' does not match "
                f"deterministic priority '{expected_priority_val}' for signals {true_signals}."
            )

        is_ambiguous = item.get("is_ambiguous")
        if not isinstance(is_ambiguous, bool):
            raise ValueError(f"Ticket {tid}: is_ambiguous must be a boolean.")

        secondary = item.get("secondary_category")
        if is_ambiguous:
            if not secondary or secondary == true_cat:
                raise ValueError(
                    f"Ticket {tid}: ambiguous ticket must have non-null secondary_category != true_category."
                )
            if secondary not in known_categories:
                raise ValueError(f"Ticket {tid}: secondary_category '{secondary}' not in known categories.")
        else:
            if secondary is not None:
                raise ValueError(f"Ticket {tid}: non-ambiguous ticket must have secondary_category=None.")

        # Derived fields in code (A2)
        body_text = item.get("body", "")
        is_hinglish = (language == "hinglish")
        is_short = len(body_text.split()) < 12
        base_queue = triage_config.category_to_queue.get(true_cat, "General")
        true_queue = expected_priority.queue_override if expected_priority.queue_override else base_queue

        ticket = EvalTicket(
            id=tid,
            subject=item.get("subject"),
            body=body_text,
            channel=channel,
            language=language,
            true_category=true_cat,
            true_signals=true_signals,
            true_priority=actual_priority,
            is_ambiguous=is_ambiguous,
            secondary_category=secondary,
            true_queue=true_queue,
            is_hinglish=is_hinglish,
            is_short=is_short,
        )
        tickets.append(ticket)

    return tickets


def select_sample(tickets: list[EvalTicket], n: int) -> list[EvalTicket]:
    """Select a deterministic sample of size n.

    - If n >= len(tickets): returns all tickets in original file order.
    - If n < len(tickets): stratified deterministic sample:
      groups tickets by true_category in alphabetical order of category,
      takes tickets round-robin across categories until n tickets are selected,
      preserving within-category file order.
    """
    if n >= len(tickets):
        return list(tickets)

    sorted_categories = sorted(list({t.true_category for t in tickets}))
    by_category: dict[str, list[EvalTicket]] = {
        cat: [t for t in tickets if t.true_category == cat]
        for cat in sorted_categories
    }

    pointers: dict[str, int] = {cat: 0 for cat in sorted_categories}
    sample: list[EvalTicket] = []

    while len(sample) < n:
        added_any = False
        for cat in sorted_categories:
            if len(sample) >= n:
                break
            cat_list = by_category[cat]
            ptr = pointers[cat]
            if ptr < len(cat_list):
                sample.append(cat_list[ptr])
                pointers[cat] = ptr + 1
                added_any = True
        if not added_any:
            break

    return sample
