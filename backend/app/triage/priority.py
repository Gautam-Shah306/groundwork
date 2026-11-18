"""Pure deterministic priority evaluation function (no LLM involvement)."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from app.triage.config import PriorityLevel, TriageConfig, load_triage_config


class PriorityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: PriorityLevel
    rule_id: str
    queue_override: str | None = None
    matched_signals: list[str]


def evaluate_priority(
    signals: set[str] | Iterable[str],
    config: TriageConfig | None = None,
) -> PriorityDecision:
    """Deterministically evaluate ticket priority from closed-vocabulary signals."""
    triage_config = config if config is not None else load_triage_config()
    signal_set = set(signals)

    known_signals = set(triage_config.signals.keys())
    unknown = sorted(signal_set - known_signals)
    if unknown:
        raise ValueError(f"Unknown signal(s): {', '.join(unknown)}")

    for rule in triage_config.rules:
        all_ok = all(sig in signal_set for sig in rule.all_of) if rule.all_of else True
        any_ok = any(sig in signal_set for sig in rule.any_of) if rule.any_of else True

        if not (all_ok and any_ok):
            continue

        rule_signals = set(rule.all_of) | set(rule.any_of)
        if rule.only_if_no_other_signals and not signal_set.issubset(rule_signals):
            continue

        matched = sorted(signal_set & rule_signals)
        return PriorityDecision(
            priority=rule.priority,
            rule_id=rule.id,
            queue_override=rule.queue_override,
            matched_signals=matched,
        )

    return PriorityDecision(
        priority=triage_config.default_priority.priority,
        rule_id=triage_config.default_priority.rule_id,
        queue_override=None,
        matched_signals=[],
    )
