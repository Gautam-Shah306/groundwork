"""Deterministic evaluation metrics calculation for Support Triage (B4).

Pure functions; never raises on partial or empty data; never mutates inputs;
all floats rounded to 4 decimals unless specified; percentage fields in summary rounded to 1 decimal.
"""

from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel, Field

from app.evaluation.dataset import EvalTicket
from app.triage.config import TriageConfig, load_triage_config
from app.triage.priority import evaluate_priority


class EvalItemRecord(BaseModel):
    """Normalized record of an evaluation prediction item for metrics calculation."""

    ticket_id: str
    status: str = "success"  # "success" or "error"
    error_code: str | None = None
    predicted_category: str | None = None
    predicted_secondary: str | None = None
    predicted_signals: list[str] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
    predicted_priority: str | None = None
    rule_id: str | None = None
    predicted_queue: str | None = None
    escalation: bool = False
    draft: dict[str, Any] | None = None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Compute the Wilson score interval for a binomial proportion.

    Formula:
        (p + z^2 / (2n) +- z * sqrt(p(1-p)/n + z^2 / (4n^2))) / (1 + z^2 / n)
    Clamped to [0.0, 1.0]. When n <= 0, returns None.
    """
    if n <= 0:
        return None
    if k < 0:
        return (0.0, 0.0)

    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    variance_term = (p * (1.0 - p)) / n + (z * z) / (4.0 * (n * n))
    spread = (z * math.sqrt(max(0.0, variance_term))) / denom

    low = max(0.0, min(1.0, center - spread))
    high = max(0.0, min(1.0, center + spread))
    return (round(low, 4), round(high, 4))


def _extract_signal_names(signals_data: Any) -> list[str]:
    """Extract list of signal name strings from either string list or dict list."""
    if not signals_data:
        return []
    result: list[str] = []
    for s in signals_data:
        if isinstance(s, str):
            result.append(s)
        elif isinstance(s, dict) and "signal" in s:
            result.append(str(s["signal"]))
    return result


def compute_evaluation_metrics(
    items: list[EvalItemRecord | dict[str, Any]],
    tickets: list[EvalTicket],
    draft_flags_checked: int = 0,
    config: TriageConfig | None = None,
) -> dict[str, Any]:
    """Compute comprehensive triage evaluation metrics from prediction items and test set tickets."""
    triage_config = config if config is not None else load_triage_config()
    total_tickets = len(tickets)

    # Index items by ticket_id
    items_by_id: dict[str, EvalItemRecord] = {}
    for item in items:
        if isinstance(item, dict):
            rec_dict = dict(item)
            if "predicted_signals" in rec_dict:
                rec_dict["predicted_signals"] = _extract_signal_names(rec_dict["predicted_signals"])
            rec = EvalItemRecord(**rec_dict)
        else:
            rec = item
            if rec.predicted_signals and isinstance(rec.predicted_signals[0], dict):
                rec = rec.model_copy(
                    update={"predicted_signals": _extract_signal_names(rec.predicted_signals)}
                )
        items_by_id[rec.ticket_id] = rec

    # Pre-calculate expected queues and ground truth decisions for tickets
    expected_data_by_id: dict[str, dict[str, Any]] = {}
    for t in tickets:
        decision = evaluate_priority(t.true_signals, config=triage_config)
        base_queue = triage_config.category_to_queue.get(t.true_category, "General")
        expected_queue = decision.queue_override if decision.queue_override else base_queue
        expected_escalation = bool(decision.queue_override or decision.priority == "high")
        expected_data_by_id[t.id] = {
            "queue": expected_queue,
            "escalation": expected_escalation,
            "rule_id": decision.rule_id,
        }

    # Counters
    completed_count = 0
    failed_count = 0
    correct_category_count = 0
    lenient_category_count = 0
    correct_priority_count = 0
    correct_queue_count = 0
    reviewer_intervention_count = 0

    # Per-category tracking
    all_categories = sorted([c.id for c in triage_config.categories])
    cat_support: dict[str, int] = {cat: 0 for cat in all_categories}
    cat_pred_count: dict[str, int] = {cat: 0 for cat in all_categories}
    cat_tp: dict[str, int] = {cat: 0 for cat in all_categories}

    # Category confusion matrix: rows=true, cols=predicted + 'no_prediction'
    cat_matrix: dict[str, dict[str, int]] = {
        true_cat: {pred_cat: 0 for pred_cat in all_categories + ["no_prediction"]}
        for true_cat in all_categories
    }

    # Priority tracking
    priority_levels = ["high", "medium", "low"]
    pri_level_num = {"high": 3, "medium": 2, "low": 1}
    pri_matrix: dict[str, dict[str, int]] = {
        true_p: {pred_p: 0 for pred_p in priority_levels + ["no_prediction"]}
        for true_p in priority_levels
    }
    under_prioritised_count = 0
    over_prioritised_count = 0
    missed_high_count = 0
    completed_truth_high_count = 0
    truth_high_count = 0
    truth_high_no_pred_count = 0

    priority_errors_by_cause = {
        "signals_exact_but_priority_wrong": 0,
        "signals_missed": 0,
        "signals_spurious": 0,
        "signals_both": 0,
        "model_failure": 0,
    }

    # Signals tracking
    all_signals = sorted(list(triage_config.signals.keys()))
    sig_support: dict[str, int] = {sig: 0 for sig in all_signals}
    sig_pred_count: dict[str, int] = {sig: 0 for sig in all_signals}
    sig_tp: dict[str, int] = {sig: 0 for sig in all_signals}
    exact_signal_matches = 0
    total_sig_tp = 0
    total_sig_fp = 0
    total_sig_fn = 0

    # Process all tickets
    for t in tickets:
        item = items_by_id.get(t.id)
        is_success = item is not None and item.status == "success"
        if is_success:
            completed_count += 1
        else:
            failed_count += 1

        true_cat = t.true_category
        cat_support[true_cat] = cat_support.get(true_cat, 0) + 1

        true_p = t.true_priority
        if true_p == "high":
            truth_high_count += 1
            if is_success:
                completed_truth_high_count += 1

        expected_q = expected_data_by_id[t.id]["queue"]

        # 1. Category evaluation
        pred_cat = item.predicted_category if (is_success and item) else None
        if pred_cat in all_categories:
            cat_pred_count[pred_cat] += 1
            cat_matrix[true_cat][pred_cat] += 1
        else:
            cat_matrix[true_cat]["no_prediction"] += 1

        is_cat_correct = False
        is_lenient_correct = False
        if is_success and item and item.predicted_category:
            if item.predicted_category == true_cat:
                correct_category_count += 1
                cat_tp[true_cat] += 1
                is_cat_correct = True
                is_lenient_correct = True
            elif t.is_ambiguous and item.predicted_category == t.secondary_category:
                is_lenient_correct = True

        if is_lenient_correct:
            lenient_category_count += 1

        # 2. Priority evaluation
        # Priority rule: predicted priority is evaluate_priority on predicted (post-processed) signals
        is_pri_correct = False
        if is_success and item:
            clean_pred_signals = [s for s in item.predicted_signals if s in triage_config.signals]
            pred_decision = evaluate_priority(clean_pred_signals, config=triage_config)
            pred_p = pred_decision.priority.value if hasattr(pred_decision.priority, "value") else str(pred_decision.priority)
            if pred_p in priority_levels:
                pri_matrix[true_p][pred_p] += 1
            else:
                pri_matrix[true_p]["no_prediction"] += 1

            if pred_p == true_p:
                correct_priority_count += 1
                is_pri_correct = True
            else:
                pred_num = pri_level_num.get(pred_p, 0)
                true_num = pri_level_num.get(true_p, 0)
                if true_num > pred_num:
                    under_prioritised_count += 1
                elif true_num < pred_num:
                    over_prioritised_count += 1

                if true_p == "high" and pred_p != "high":
                    missed_high_count += 1
        else:
            pred_p = None
            pri_matrix[true_p]["no_prediction"] += 1
            if true_p == "high":
                truth_high_no_pred_count += 1

        # Priority error causes
        if not is_pri_correct:
            if not is_success or item is None:
                priority_errors_by_cause["model_failure"] += 1
            else:
                pred_sig_set = set(item.predicted_signals)
                true_sig_set = set(t.true_signals)
                if pred_sig_set == true_sig_set:
                    priority_errors_by_cause["signals_exact_but_priority_wrong"] += 1
                else:
                    missed = bool(true_sig_set - pred_sig_set)
                    spurious = bool(pred_sig_set - true_sig_set)
                    if missed and spurious:
                        priority_errors_by_cause["signals_both"] += 1
                    elif missed:
                        priority_errors_by_cause["signals_missed"] += 1
                    elif spurious:
                        priority_errors_by_cause["signals_spurious"] += 1

        # 3. Queue evaluation
        is_queue_correct = False
        if is_success and item and item.predicted_queue == expected_q:
            correct_queue_count += 1
            is_queue_correct = True

        # 4. Reviewer change proxy (R1/A1):
        # Share of evaluated tickets where category OR priority OR queue is wrong, or there is no prediction.
        # (Signals are NOT part of it; labelled a proxy, not an override rate.)
        if (not is_success) or (not is_cat_correct) or (not is_pri_correct) or (not is_queue_correct):
            reviewer_intervention_count += 1

        # 5. Signals evaluation
        true_sig_set = set(t.true_signals)
        pred_sig_set = set(item.predicted_signals) if (is_success and item) else set()

        for sig in true_sig_set:
            if sig in sig_support:
                sig_support[sig] += 1
        for sig in pred_sig_set:
            if sig in sig_pred_count:
                sig_pred_count[sig] += 1

        tp_set = true_sig_set & pred_sig_set
        for sig in tp_set:
            if sig in sig_tp:
                sig_tp[sig] += 1

        total_sig_tp += len(tp_set)
        total_sig_fp += len(pred_sig_set - true_sig_set)
        total_sig_fn += len(true_sig_set - pred_sig_set)

        if pred_sig_set == true_sig_set:
            exact_signal_matches += 1

    # Wilson interval for category accuracy
    cat_wilson = wilson(correct_category_count, total_tickets)
    cat_wilson_list = list(cat_wilson) if cat_wilson is not None else [0.0, 0.0]

    # Per-category P, R, F1
    per_category: dict[str, dict[str, Any]] = {}
    f1_list: list[float] = []
    for cat in all_categories:
        sup = cat_support[cat]
        pred_c = cat_pred_count[cat]
        tp = cat_tp[cat]
        p = round(tp / pred_c, 4) if pred_c > 0 else 0.0
        r = round(tp / sup, 4) if sup > 0 else 0.0
        f1 = round((2.0 * p * r) / (p + r), 4) if (p + r) > 0.0 else 0.0
        f1_list.append(f1)
        per_category[cat] = {
            "support": sup,
            "predicted_count": pred_c,
            "precision": p,
            "recall": r,
            "f1": f1,
        }
    macro_f1 = round(sum(f1_list) / len(f1_list), 4) if f1_list else 0.0

    # Signals micro metrics
    sig_p_denom = total_sig_tp + total_sig_fp
    sig_r_denom = total_sig_tp + total_sig_fn
    sig_micro_p = round(total_sig_tp / sig_p_denom, 4) if sig_p_denom > 0 else 0.0
    sig_micro_r = round(total_sig_tp / sig_r_denom, 4) if sig_r_denom > 0 else 0.0
    sig_micro_f1 = (
        round((2.0 * sig_micro_p * sig_micro_r) / (sig_micro_p + sig_micro_r), 4)
        if (sig_micro_p + sig_micro_r) > 0.0
        else 0.0
    )
    exact_set_match_rate = round(exact_signal_matches / total_tickets, 4) if total_tickets > 0 else 0.0

    per_signal: dict[str, dict[str, Any]] = {}
    for sig in all_signals:
        sup = sig_support[sig]
        pc = sig_pred_count[sig]
        tp = sig_tp[sig]
        p = round(tp / pc, 4) if pc > 0 else 0.0
        r = round(tp / sup, 4) if sup > 0 else 0.0
        f1 = round((2.0 * p * r) / (p + r), 4) if (p + r) > 0.0 else 0.0
        per_signal[sig] = {
            "support": sup,
            "predicted_count": pc,
            "precision": p,
            "recall": r,
            "f1": f1,
        }

    # Slices (A2/B4):
    # language en, hinglish; is_ambiguous; short (<12 words); urgency_or_delay
    slice_defs = {
        "en": lambda t: t.language == "en",
        "hinglish": lambda t: t.language == "hinglish" or getattr(t, "is_hinglish", False),
        "is_ambiguous": lambda t: bool(t.is_ambiguous),
        "short": lambda t: getattr(t, "is_short", len(t.body.split()) < 12),
        "urgency_or_delay": lambda t: (
            "explicit_urgency" in t.true_signals or "delivery_delayed_over_3_days" in t.true_signals
        ),
    }

    slices: list[dict[str, Any]] = []
    for slice_name, predicate in slice_defs.items():
        slice_tickets = [t for t in tickets if predicate(t)]
        cnt = len(slice_tickets)
        correct_c = 0
        correct_p = 0
        for t in slice_tickets:
            item = items_by_id.get(t.id)
            if item and item.status == "success":
                if item.predicted_category == t.true_category:
                    correct_c += 1
                # Check priority
                clean_sigs = [s for s in item.predicted_signals if s in triage_config.signals]
                dec = evaluate_priority(clean_sigs, config=triage_config)
                p_val = dec.priority.value if hasattr(dec.priority, "value") else str(dec.priority)
                if p_val == t.true_priority:
                    correct_p += 1
        slices.append({
            "name": slice_name,
            "count": cnt,
            "category_accuracy": round(correct_c / cnt, 4) if cnt > 0 else 0.0,
            "priority_accuracy": round(correct_p / cnt, 4) if cnt > 0 else 0.0,
            "low_confidence": cnt < 30,
        })

    # Failure case selection (at most 5 items) - A1:
    # Order:
    # 1. true high predicted lower (medium/low)
    # 2. wrong category
    # 3. wrong priority
    # 4. no prediction (failed items)
    # Ties by ticket_id ascending; at most 5; reason sentence generated by code.
    bucket_1: list[dict[str, Any]] = []
    bucket_2: list[dict[str, Any]] = []
    bucket_3: list[dict[str, Any]] = []
    bucket_4: list[dict[str, Any]] = []

    for t in tickets:
        item = items_by_id.get(t.id)
        if not item or item.status != "success":
            bucket_4.append({
                "ticket_id": t.id,
                "subject": t.subject,
                "body": t.body,
                "body_snippet": t.body[:100],
                "language": t.language,
                "true_category": t.true_category,
                "predicted_category": None,
                "true_priority": t.true_priority,
                "predicted_priority": None,
                "true_signals": t.true_signals,
                "predicted_signals": [],
                "flags": item.flags if item else [],
                "reason": f"Classification failed ({item.error_code if item else 'missing_item'}).",
            })
            continue

        clean_sigs = [s for s in item.predicted_signals if s in triage_config.signals]
        dec = evaluate_priority(clean_sigs, config=triage_config)
        pred_p = dec.priority.value if hasattr(dec.priority, "value") else str(dec.priority)

        cat_wrong = item.predicted_category != t.true_category
        pri_wrong = pred_p != t.true_priority
        true_is_high = t.true_priority == "high"
        pred_is_lower = pred_p in ("medium", "low")

        case_dict = {
            "ticket_id": t.id,
            "subject": t.subject,
            "body": t.body,
            "body_snippet": t.body[:100],
            "language": t.language,
            "true_category": t.true_category,
            "predicted_category": item.predicted_category,
            "true_priority": t.true_priority,
            "predicted_priority": pred_p,
            "true_signals": t.true_signals,
            "predicted_signals": item.predicted_signals,
            "flags": item.flags or [],
        }

        if true_is_high and pred_is_lower:
            case_dict["reason"] = f"High priority ticket under-prioritised to {pred_p}."
            bucket_1.append(case_dict)
        elif cat_wrong:
            case_dict["reason"] = f"Category misclassified as {item.predicted_category} (expected {t.true_category})."
            bucket_2.append(case_dict)
        elif pri_wrong:
            case_dict["reason"] = f"Priority misclassified as {pred_p} (expected {t.true_priority})."
            bucket_3.append(case_dict)

    # Sort each bucket by ticket_id ascending
    for b in [bucket_1, bucket_2, bucket_3, bucket_4]:
        b.sort(key=lambda x: str(x["ticket_id"]))

    failure_cases: list[dict[str, Any]] = []
    for b in [bucket_1, bucket_2, bucket_3, bucket_4]:
        for case in b:
            if len(failure_cases) < 5:
                failure_cases.append(case)
            else:
                break
        if len(failure_cases) >= 5:
            break

    # Draft flag checks (A5)
    draft_metrics: dict[str, Any] | None = None
    evaluated_drafts = [it for it in items_by_id.values() if it.draft is not None]
    if evaluated_drafts or draft_flags_checked > 0:
        d_count = len(evaluated_drafts)
        total_flags = 0
        flag_codes: dict[str, int] = {}
        tickets_with_flags = 0
        draft_unavailable_count = 0

        for it in evaluated_drafts:
            d_dict = it.draft or {}
            flags = d_dict.get("flags") or []
            if d_dict.get("draft_unavailable", False) or d_dict.get("error_code"):
                draft_unavailable_count += 1
            if flags:
                tickets_with_flags += 1
                total_flags += len(flags)
            for f in flags:
                code = f.get("code", "unknown") if isinstance(f, dict) else str(f)
                flag_codes[code] = flag_codes.get(code, 0) + 1
                if code == "draft_unavailable":
                    draft_unavailable_count += 1

        unflagged_count = d_count - tickets_with_flags
        unflagged_rate = round(unflagged_count / d_count, 4) if d_count > 0 else 0.0
        flag_rate = round(tickets_with_flags / d_count, 4) if d_count > 0 else 0.0

        draft_metrics = {
            "n": d_count,
            "count": d_count,
            "tickets_with_flags": tickets_with_flags,
            "flag_rate": flag_rate,
            "total_flags": total_flags,
            "counts_by_flag_code": flag_codes,
            "flag_counts_by_code": flag_codes,
            "draft_unavailable_count": draft_unavailable_count,
            "unflagged_rate": unflagged_rate,
            "note": "Automated checks only: this does not measure reply quality.",
        }

    # Summary dictionary
    cat_acc = round(correct_category_count / total_tickets, 4) if total_tickets > 0 else 0.0
    cat_acc_completed = round(correct_category_count / completed_count, 4) if completed_count > 0 else 0.0
    lenient_cat_acc = round(lenient_category_count / total_tickets, 4) if total_tickets > 0 else 0.0
    pri_acc = round(correct_priority_count / total_tickets, 4) if total_tickets > 0 else 0.0
    pri_acc_completed = round(correct_priority_count / completed_count, 4) if completed_count > 0 else 0.0
    queue_acc = round(correct_queue_count / total_tickets, 4) if total_tickets > 0 else 0.0
    reviewer_proxy = round(reviewer_intervention_count / total_tickets, 4) if total_tickets > 0 else 0.0

    summary = {
        "total_tickets": total_tickets,
        "completed": completed_count,
        "failed": failed_count,
        "category_accuracy": cat_acc,
        "category_accuracy_completed": cat_acc_completed,
        "category_accuracy_wilson": cat_wilson_list,
        "lenient_category_accuracy": lenient_cat_acc,
        "priority_accuracy": pri_acc,
        "priority_accuracy_completed": pri_acc_completed,
        "queue_accuracy": queue_acc,
        "reviewer_change_proxy": reviewer_proxy,
        "missed_high_count": missed_high_count,
        # Percentage representations (1 decimal place)
        "category_accuracy_pct": round(cat_acc * 100, 1),
        "priority_accuracy_pct": round(pri_acc * 100, 1),
        "queue_accuracy_pct": round(queue_acc * 100, 1),
        "reviewer_change_proxy_pct": round(reviewer_proxy * 100, 1),
    }

    under_prioritised_share = round(under_prioritised_count / completed_count, 4) if completed_count > 0 else 0.0
    over_prioritised_share = round(over_prioritised_count / completed_count, 4) if completed_count > 0 else 0.0
    missed_high_rate = round(missed_high_count / completed_truth_high_count, 4) if completed_truth_high_count > 0 else 0.0
    truth_high_no_pred_rate = round(truth_high_no_pred_count / truth_high_count, 4) if truth_high_count > 0 else 0.0

    priority_metrics = {
        "priority_accuracy": pri_acc,
        "priority_accuracy_completed": pri_acc_completed,
        "strict_accuracy": pri_acc,
        "completed_accuracy": pri_acc_completed,
        "confusion_matrix": pri_matrix,
        "under_prioritised": under_prioritised_count,
        "under_prioritised_share": under_prioritised_share,
        "over_prioritised": over_prioritised_count,
        "over_prioritised_share": over_prioritised_share,
        "missed_high": {
            "count": missed_high_count,
            "rate": missed_high_rate,
        },
        "truth_high_no_prediction": {
            "count": truth_high_no_pred_count,
            "rate": truth_high_no_pred_rate,
        },
        "priority_errors_by_cause": priority_errors_by_cause,
    }

    signals_metrics = {
        "micro_precision": sig_micro_p,
        "micro_recall": sig_micro_r,
        "micro_f1": sig_micro_f1,
        "exact_set_match_rate": exact_set_match_rate,
        "per_signal": per_signal,
    }

    return {
        "summary": summary,
        "per_category": per_category,
        "macro_f1": macro_f1,
        "category_confusion_matrix": cat_matrix,
        "priority_metrics": priority_metrics,
        "signals_metrics": signals_metrics,
        "slices": slices,
        "failure_cases": failure_cases,
        "draft_checks": draft_metrics,
        "draft_check": draft_metrics,
    }
