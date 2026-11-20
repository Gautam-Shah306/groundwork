"""Tests for deterministic evaluation metrics calculation (B4)."""

from __future__ import annotations

import pytest

from app.evaluation.dataset import EvalTicket, load_eval_tickets
from app.evaluation.metrics import (
    EvalItemRecord,
    compute_evaluation_metrics,
    wilson,
)
from app.triage.config import load_triage_config


# 19. test_wilson_score_interval_formula
def test_wilson_score_interval_formula() -> None:
    low, high = wilson(120, 150)
    assert 0.72 < low < 0.75
    assert 0.85 < high < 0.87
    # 0 successes
    low_0, high_0 = wilson(0, 100)
    assert low_0 == 0.0
    assert high_0 > 0.0
    # all successes
    low_1, high_1 = wilson(100, 100)
    assert low_1 < 1.0
    assert high_1 == 1.0


# 20. test_wilson_returns_zero_on_empty_sample
def test_wilson_returns_zero_on_empty_sample() -> None:
    assert wilson(0, 0) == (0.0, 0.0)
    assert wilson(5, 0) == (0.0, 0.0)


# 21. test_summary_metrics_perfect_predictions
def test_summary_metrics_perfect_predictions() -> None:
    tickets = load_eval_tickets()
    config = load_triage_config()
    cat_queue = {c.id: c.queue for c in config.categories}
    items = []
    for t in tickets:
        q = "Escalations" if "legal_or_chargeback_threat" in t.true_signals else cat_queue.get(t.true_category, "General")
        esc = bool("legal_or_chargeback_threat" in t.true_signals or t.true_priority == "high")
        items.append(
            EvalItemRecord(
                ticket_id=t.id,
                status="success",
                predicted_category=t.true_category,
                predicted_priority=t.true_priority,
                predicted_signals=t.true_signals,
                predicted_queue=q,
                escalation=esc,
            )
        )
    res = compute_evaluation_metrics(items, tickets, config=config)
    summary = res["summary"]
    assert summary["category_accuracy"] == 1.0
    assert summary["category_accuracy_completed"] == 1.0
    assert summary["priority_accuracy"] == 1.0
    assert summary["queue_accuracy"] == 1.0
    assert summary["reviewer_change_proxy"] == 0.0
    assert summary["completed"] == len(tickets)
    assert summary["failed"] == 0


# 22. test_summary_metrics_all_failed_items
def test_summary_metrics_all_failed_items() -> None:
    tickets = load_eval_tickets()
    items = [
        EvalItemRecord(
            ticket_id=t.id,
            status="error",
            error_code="rate_limit",
        )
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    summary = res["summary"]
    assert summary["completed"] == 0
    assert summary["failed"] == len(tickets)
    assert summary["category_accuracy"] == 0.0
    assert summary["category_accuracy_completed"] == 0.0
    assert summary["priority_accuracy"] == 0.0
    assert summary["reviewer_change_proxy"] == 1.0
    assert res["priority_metrics"]["priority_errors_by_cause"]["model_failure"] == len(tickets)


# 23. test_summary_metrics_category_accuracy_counts_failed_as_incorrect
def test_summary_metrics_category_accuracy_counts_failed_as_incorrect() -> None:
    tickets = load_eval_tickets()[:10]
    # 5 correct, 5 failed
    items = []
    for i, t in enumerate(tickets):
        if i < 5:
            items.append(EvalItemRecord(ticket_id=t.id, status="success", predicted_category=t.true_category, predicted_priority=t.true_priority))
        else:
            items.append(EvalItemRecord(ticket_id=t.id, status="error", error_code="timeout"))
    res = compute_evaluation_metrics(items, tickets)
    summary = res["summary"]
    assert summary["category_accuracy"] == 0.5
    assert summary["category_accuracy_completed"] == 1.0


# 24. test_lenient_category_accuracy_credits_secondary_only_when_ambiguous
def test_lenient_category_accuracy_credits_secondary_only_when_ambiguous() -> None:
    tickets = load_eval_tickets()
    ambiguous_ticket = next(t for t in tickets if t.is_ambiguous)
    non_ambiguous_ticket = next(t for t in tickets if not t.is_ambiguous)

    # Predict secondary on ambiguous -> lenient should credit
    item_amb = EvalItemRecord(
        ticket_id=ambiguous_ticket.id,
        status="success",
        predicted_category=ambiguous_ticket.secondary_category,
        predicted_priority=ambiguous_ticket.true_priority,
    )
    # Predict wrong on non-ambiguous -> lenient should not credit
    item_non_amb = EvalItemRecord(
        ticket_id=non_ambiguous_ticket.id,
        status="success",
        predicted_category="damaged_item" if non_ambiguous_ticket.true_category != "damaged_item" else "order_tracking",
        predicted_priority=non_ambiguous_ticket.true_priority,
    )

    subset = [ambiguous_ticket, non_ambiguous_ticket]
    res = compute_evaluation_metrics([item_amb, item_non_amb], subset)
    assert res["summary"]["category_accuracy"] == 0.0
    assert res["summary"]["lenient_category_accuracy"] == 0.5


# 25. test_per_category_precision_recall_f1_and_macro_f1
def test_per_category_precision_recall_f1_and_macro_f1() -> None:
    tickets = load_eval_tickets()
    # Predict everything as order_tracking
    items = [
        EvalItemRecord(
            ticket_id=t.id,
            status="success",
            predicted_category="order_tracking",
            predicted_priority="low",
        )
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    ot = res["per_category"]["order_tracking"]
    assert ot["recall"] == 1.0
    assert ot["precision"] == round(ot["support"] / len(tickets), 4)
    assert res["macro_f1"] < 1.0


# 26. test_category_confusion_matrix_has_no_prediction_column
def test_category_confusion_matrix_has_no_prediction_column() -> None:
    tickets = load_eval_tickets()[:5]
    items = [
        EvalItemRecord(ticket_id=t.id, status="error", error_code="fail")
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    matrix = res["category_confusion_matrix"]
    for true_cat in matrix:
        assert "no_prediction" in matrix[true_cat]
        # For the 5 tickets, no_prediction count must be > 0
        if any(t.true_category == true_cat for t in tickets):
            assert matrix[true_cat]["no_prediction"] > 0


# 27. test_priority_confusion_matrix_3x3_plus_no_prediction
def test_priority_confusion_matrix_3x3_plus_no_prediction() -> None:
    tickets = load_eval_tickets()
    items = [
        EvalItemRecord(ticket_id=t.id, status="success", predicted_category=t.true_category, predicted_priority="medium")
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    matrix = res["priority_metrics"]["confusion_matrix"]
    assert set(matrix.keys()) == {"high", "medium", "low"}
    for row in matrix.values():
        assert set(row.keys()) == {"high", "medium", "low", "no_prediction"}


# 28. test_priority_under_and_over_prioritised_counts
def test_priority_under_and_over_prioritised_counts() -> None:
    t_high = EvalTicket(id="EV-100", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["item_damaged_or_defective"], true_priority="high", is_ambiguous=False)
    t_low = EvalTicket(id="EV-101", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=[], true_priority="low", is_ambiguous=False)

    # Predict low for high (under-prioritised), predict high for low (over-prioritised)
    i_high = EvalItemRecord(ticket_id="EV-100", status="success", predicted_category="order_tracking", predicted_priority="low")
    i_low = EvalItemRecord(ticket_id="EV-101", status="success", predicted_category="order_tracking", predicted_priority="high")

    res = compute_evaluation_metrics([i_high, i_low], [t_high, t_low])
    pm = res["priority_metrics"]
    assert pm["under_prioritised"] == 1
    assert pm["over_prioritised"] == 1


# 29. test_missed_high_count_and_rate
def test_missed_high_count_and_rate() -> None:
    t_high1 = EvalTicket(id="EV-100", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["item_damaged_or_defective"], true_priority="high", is_ambiguous=False)
    t_high2 = EvalTicket(id="EV-101", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["item_damaged_or_defective"], true_priority="high", is_ambiguous=False)

    # One predicted medium, one error
    i1 = EvalItemRecord(ticket_id="EV-100", status="success", predicted_category="order_tracking", predicted_priority="medium")
    i2 = EvalItemRecord(ticket_id="EV-101", status="error", error_code="timeout")

    res = compute_evaluation_metrics([i1, i2], [t_high1, t_high2])
    pm = res["priority_metrics"]
    assert pm["missed_high"]["count"] == 2
    assert pm["missed_high"]["rate"] == 1.0
    assert pm["truth_high_no_prediction"]["count"] == 1
    assert pm["truth_high_no_prediction"]["rate"] == 0.5


# 30. test_priority_errors_by_cause_signals_exact_is_always_zero
def test_priority_errors_by_cause_signals_exact_is_always_zero() -> None:
    tickets = load_eval_tickets()
    # When signals are extracted, priority is computed deterministically from those signals.
    # Therefore, whenever predicted_signals == true_signals, predicted_priority == true_priority,
    # and signals_exact_but_priority_wrong is always 0.
    items = [
        EvalItemRecord(
            ticket_id=t.id,
            status="success",
            predicted_category=t.true_category,
            predicted_signals=t.true_signals,
            predicted_priority=t.true_priority,
        )
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    causes = res["priority_metrics"]["priority_errors_by_cause"]
    assert causes["signals_exact_but_priority_wrong"] == 0


# 31. test_priority_errors_by_cause_categorises_missed_spurious_both
def test_priority_errors_by_cause_categorises_missed_spurious_both() -> None:
    t1 = EvalTicket(id="EV-101", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["item_damaged_or_defective"], true_priority="high", is_ambiguous=False)
    t2 = EvalTicket(id="EV-102", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=[], true_priority="low", is_ambiguous=False)
    t3 = EvalTicket(id="EV-103", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["delivery_delayed_over_3_days"], true_priority="medium", is_ambiguous=False)

    # t1: missed signal
    i1 = EvalItemRecord(ticket_id="EV-101", status="success", predicted_signals=[], predicted_priority="low")
    # t2: spurious signal
    i2 = EvalItemRecord(ticket_id="EV-102", status="success", predicted_signals=["item_damaged_or_defective"], predicted_priority="high")
    # t3: both missed and spurious
    i3 = EvalItemRecord(ticket_id="EV-103", status="success", predicted_signals=["item_damaged_or_defective"], predicted_priority="high")

    res = compute_evaluation_metrics([i1, i2, i3], [t1, t2, t3])
    causes = res["priority_metrics"]["priority_errors_by_cause"]
    assert causes["signals_missed"] == 1
    assert causes["signals_spurious"] == 1
    assert causes["signals_both"] == 1


# 32. test_signals_micro_precision_recall_f1_and_exact_match_rate
def test_signals_micro_precision_recall_f1_and_exact_match_rate() -> None:
    t = EvalTicket(id="EV-101", body="b", channel="chat", language="en", true_category="order_tracking", true_signals=["item_damaged_or_defective"], true_priority="high", is_ambiguous=False)
    i = EvalItemRecord(ticket_id="EV-101", status="success", predicted_signals=["item_damaged_or_defective"], predicted_priority="high")
    res = compute_evaluation_metrics([i], [t])
    sm = res["signals_metrics"]
    assert sm["micro_precision"] == 1.0
    assert sm["micro_recall"] == 1.0
    assert sm["micro_f1"] == 1.0
    assert sm["exact_set_match_rate"] == 1.0


# 33. test_slices_all_five_slices_present_with_low_confidence_flag
def test_slices_all_five_slices_present_with_low_confidence_flag() -> None:
    tickets = load_eval_tickets()
    items = [
        EvalItemRecord(ticket_id=t.id, status="success", predicted_category=t.true_category, predicted_priority=t.true_priority)
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    slices = res["slices"]
    names = {s["name"] for s in slices}
    assert names == {"en", "hinglish", "is_ambiguous", "short", "urgency_or_delay"}
    for s in slices:
        assert s["low_confidence"] == (s["count"] < 30)


# 34. test_failure_cases_selects_up_to_5_in_exact_severity_order
def test_failure_cases_selects_up_to_5_in_exact_severity_order() -> None:
    tickets = load_eval_tickets()
    # Create deliberate errors
    items = []
    for t in tickets:
        if t.true_priority == "high":
            # Bucket 1: missed high
            items.append(EvalItemRecord(ticket_id=t.id, status="success", predicted_category=t.true_category, predicted_priority="low"))
        else:
            items.append(EvalItemRecord(ticket_id=t.id, status="success", predicted_category=t.true_category, predicted_priority=t.true_priority))
    res = compute_evaluation_metrics(items, tickets)
    cases = res["failure_cases"]
    assert len(cases) <= 5
    assert all("under-prioritised" in c["reason"] for c in cases)


# 35. test_failure_cases_breaks_ties_by_ticket_id_ascending
def test_failure_cases_breaks_ties_by_ticket_id_ascending() -> None:
    tickets = load_eval_tickets()
    items = [
        EvalItemRecord(ticket_id=t.id, status="error", error_code="timeout")
        for t in tickets
    ]
    res = compute_evaluation_metrics(items, tickets)
    cases = res["failure_cases"]
    assert len(cases) == 5
    ids = [c["ticket_id"] for c in cases]
    assert ids == sorted(ids)


# 36. test_draft_flag_checks_aggregates_counts_and_unflagged_rate
def test_draft_flag_checks_aggregates_counts_and_unflagged_rate() -> None:
    tickets = load_eval_tickets()[:2]
    i1 = EvalItemRecord(
        ticket_id=tickets[0].id,
        status="success",
        predicted_category=tickets[0].true_category,
        predicted_priority=tickets[0].true_priority,
        draft={"reply": "ok", "flags": [{"code": "unresolved_placeholder"}], "reviewer_note": "n", "policy_refs": []},
    )
    i2 = EvalItemRecord(
        ticket_id=tickets[1].id,
        status="success",
        predicted_category=tickets[1].true_category,
        predicted_priority=tickets[1].true_priority,
        draft={"reply": "ok", "flags": [], "reviewer_note": "n", "policy_refs": []},
    )
    res = compute_evaluation_metrics([i1, i2], tickets, draft_flags_checked=2)
    dc = res["draft_checks"]
    assert dc is not None
    assert dc["count"] == 2
    assert dc["total_flags"] == 1
    assert dc["flag_counts_by_code"]["unresolved_placeholder"] == 1
    assert dc["unflagged_rate"] == 0.5
