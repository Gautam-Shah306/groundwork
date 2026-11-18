"""Tests for triage configuration validation and deterministic priority evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.triage.config import load_triage_config
from app.triage.priority import evaluate_priority


def test_config_loads_categories_queues_and_signals() -> None:
    config = load_triage_config()

    assert [cat.id for cat in config.categories] == [
        "order_tracking",
        "returns_refunds",
        "payment_issues",
        "product_questions",
        "address_change",
        "damaged_item",
        "account_login",
    ]
    assert config.queues == [
        "Order support",
        "Returns and refunds",
        "Payments",
        "General",
        "Escalations",
    ]
    assert len(config.signals) == 10
    assert len(config.rules) == 9
    assert config.default_priority.rule_id == "R-DEFAULT"
    assert config.default_priority.priority == "medium"


def test_every_category_maps_to_exactly_one_queue() -> None:
    config = load_triage_config()
    expected = {
        "order_tracking": "Order support",
        "address_change": "Order support",
        "returns_refunds": "Returns and refunds",
        "damaged_item": "Returns and refunds",
        "payment_issues": "Payments",
        "product_questions": "General",
        "account_login": "General",
    }

    mapping = config.category_to_queue
    assert mapping == expected
    assert set(mapping.values()).issubset(set(config.queues))


def test_config_rejects_rule_referencing_unknown_signal(tmp_path: Path) -> None:
    config = load_triage_config()
    (tmp_path / "queues.yaml").write_text(
        yaml.safe_dump(config.queues_config.model_dump()), encoding="utf-8"
    )
    bad_rules = config.priority_rules_config.model_dump()
    bad_rules["rules"][0]["any_of"] = ["invented_signal_not_in_vocab"]
    (tmp_path / "priority_rules.yaml").write_text(
        yaml.safe_dump(bad_rules), encoding="utf-8"
    )

    with pytest.raises(ValidationError, match="unknown signal"):
        load_triage_config(tmp_path)


def test_config_rejects_invalid_priority_value(tmp_path: Path) -> None:
    config = load_triage_config()
    (tmp_path / "queues.yaml").write_text(
        yaml.safe_dump(config.queues_config.model_dump()), encoding="utf-8"
    )
    bad_rules = config.priority_rules_config.model_dump()
    bad_rules["rules"][0]["priority"] = "urgent_critical"
    (tmp_path / "priority_rules.yaml").write_text(
        yaml.safe_dump(bad_rules), encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        load_triage_config(tmp_path)


def test_priority_legal_threat_is_high_with_escalations_override() -> None:
    decision = evaluate_priority({"legal_or_chargeback_threat"})

    assert decision.priority == "high"
    assert decision.rule_id == "R-LEGAL"
    assert decision.queue_override == "Escalations"
    assert decision.matched_signals == ["legal_or_chargeback_threat"]


def test_priority_double_charge_is_high() -> None:
    decision = evaluate_priority({"payment_charged_twice"})

    assert decision.priority == "high"
    assert decision.rule_id == "R-PAY"
    assert decision.queue_override is None
    assert decision.matched_signals == ["payment_charged_twice"]


def test_priority_damaged_item_is_high() -> None:
    decision = evaluate_priority({"item_damaged_or_defective"})

    assert decision.priority == "high"
    assert decision.rule_id == "R-DAMAGE"
    assert decision.matched_signals == ["item_damaged_or_defective"]


def test_priority_delay_with_urgency_is_high() -> None:
    decision = evaluate_priority({"delivery_delayed_over_3_days", "explicit_urgency"})

    assert decision.priority == "high"
    assert decision.rule_id == "R-DELAY-URGENT"
    assert decision.matched_signals == ["delivery_delayed_over_3_days", "explicit_urgency"]


def test_priority_delay_without_urgency_is_medium() -> None:
    decision = evaluate_priority({"delivery_delayed_over_3_days"})

    assert decision.priority == "medium"
    assert decision.rule_id == "R-DELAY"
    assert decision.matched_signals == ["delivery_delayed_over_3_days"]


def test_priority_refund_overdue_is_medium() -> None:
    decision = evaluate_priority({"refund_overdue"})

    assert decision.priority == "medium"
    assert decision.rule_id == "R-REFUND"
    assert decision.matched_signals == ["refund_overdue"]


def test_priority_general_inquiry_only_is_low() -> None:
    decision = evaluate_priority({"general_inquiry"})

    assert decision.priority == "low"
    assert decision.rule_id == "R-GENERAL"
    assert decision.matched_signals == ["general_inquiry"]


def test_priority_general_inquiry_with_other_signal_is_not_low() -> None:
    decision = evaluate_priority({"general_inquiry", "account_locked"})

    assert decision.priority != "low"
    assert decision.priority == "medium"
    assert decision.rule_id == "R-ACCOUNT"


def test_priority_empty_signals_returns_default_rule() -> None:
    decision = evaluate_priority(set())

    assert decision.priority == "medium"
    assert decision.rule_id == "R-DEFAULT"
    assert decision.queue_override is None
    assert decision.matched_signals == []


def test_priority_first_matching_rule_wins_when_several_match() -> None:
    decision = evaluate_priority(
        {
            "legal_or_chargeback_threat",
            "payment_charged_twice",
            "item_damaged_or_defective",
            "refund_overdue",
        }
    )

    assert decision.rule_id == "R-LEGAL"
    assert decision.priority == "high"
    assert decision.queue_override == "Escalations"


def test_priority_unknown_signal_raises() -> None:
    with pytest.raises(ValueError, match="Unknown signal"):
        evaluate_priority({"vip_customer_flag"})


def test_priority_is_deterministic_for_repeated_calls() -> None:
    signals = {"delivery_delayed_over_3_days", "explicit_urgency", "refund_overdue"}
    first = evaluate_priority(signals)
    repeated = [evaluate_priority(signals) for _ in range(10)]

    assert all(result == first for result in repeated)
