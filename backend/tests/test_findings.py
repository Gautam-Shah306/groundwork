"""Unit tests for deterministic rule-based diagnostic findings."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.findings.rules import STRENGTH_ORDER, generate_findings
from app.ingest.parse import parse_csv_bytes
from app.ingest.validate import validate_parsed_csv
from app.metrics.config import load_metrics_config
from app.metrics.frame import build_ticket_frame
from app.metrics.registry import compute_all_metrics
from app.triage.config import load_triage_config

REPO_ROOT = Path(__file__).resolve().parents[2]
IST = timezone(timedelta(hours=5, minutes=30))

BANNED_CAUSAL_PHRASES = [
    r"\bbecause\b",
    r"\bcaused\b",
    r"\bcauses\b",
    r"\bdue to\b",
    r"\bleads to\b",
    r"\bled to\b",
    r"\bresult of\b",
    r"\bresulting from\b",
    r"\bdrives\b",
    r"\bdriven by\b",
]

HEDGING_WORDS = [r"\bmay\b", r"\bmight\b", r"\bcould\b", r"\bpossible\b"]


@pytest.fixture(scope="module")
def sample_metrics_and_findings():
    metrics_config = load_metrics_config()
    triage_config = load_triage_config()
    raw_bytes = (REPO_ROOT / "data" / "sample_tickets.csv").read_bytes()
    parsed = parse_csv_bytes(raw_bytes, "sample_tickets.csv")
    validated = validate_parsed_csv(parsed, triage_config)

    records = [
        {
            "row_id": idx + 1,
            "ticket_id": r.ticket_id,
            "created_at": r.created_at,
            "assigned_at": r.assigned_at,
            "first_response_at": r.first_response_at,
            "resolved_at": r.resolved_at,
            "category": r.category,
            "priority": r.priority,
            "queue": r.queue,
            "assigned_agent": r.assigned_agent,
            "status": r.status,
            "channel": r.channel,
            "reassignment_count": r.reassignment_count,
            "customer_id": r.customer_id,
            "is_valid": r.is_valid,
            "validation_flags": r.validation_flags,
        }
        for idx, r in enumerate(validated.rows)
    ]
    frame = build_ticket_frame(records, metrics_config)
    results = compute_all_metrics(frame, metrics_config, as_of=validated.period_end)
    findings = generate_findings(results, metrics_config)
    return results, findings, metrics_config


def _by_id(findings) -> dict[str, Any]:
    return {f.id: f for f in findings}


def test_triage_finding_generated_with_evidence_refs(sample_metrics_and_findings) -> None:
    _, findings, _ = sample_metrics_and_findings
    f = _by_id(findings)["F-TRIAGE"]

    assert f.status == "supported"
    assert f.strength == "strong"
    assert any(ev.metric_id == "triage_share_of_first_response" for ev in f.evidence)
    assert any(ev.metric_id == "triage_time" for ev in f.evidence)


def test_misrouting_finding_flags_order_tracking_and_returns_refunds(
    sample_metrics_and_findings,
) -> None:
    _, findings, _ = sample_metrics_and_findings
    f = _by_id(findings)["F-MISROUTE"]

    assert f.status == "supported"
    assert f.strength == "strong"
    assert "order_tracking" in f.observation.text
    assert "returns_refunds" in f.observation.text


def test_evening_finding_generated_with_difference_in_hours(
    sample_metrics_and_findings,
) -> None:
    _, findings, _ = sample_metrics_and_findings
    f = _by_id(findings)["F-EVENING"]

    assert f.status == "supported"
    assert f.strength in ("moderate", "strong")
    assert "hours" in f.observation.text.lower()


def test_workload_finding_is_weaker_than_triage_finding_on_sample(
    sample_metrics_and_findings,
) -> None:
    _, findings, _ = sample_metrics_and_findings
    by_id = _by_id(findings)
    triage = by_id["F-TRIAGE"]
    workload = by_id["F-WORKLOAD"]

    assert triage.status == "supported"
    assert workload.status == "supported"
    assert STRENGTH_ORDER[workload.strength] > STRENGTH_ORDER[triage.strength]


def test_backlog_finding_counts_tickets_older_than_7_days(
    sample_metrics_and_findings,
) -> None:
    results, findings, _ = sample_metrics_and_findings
    f = _by_id(findings)["F-BACKLOG"]
    gte_7d = next(
        b for b in results["backlog_ageing"].data["buckets"] if b["bucket"] == "gte_7d"
    )

    assert f.status == "supported"
    assert str(gte_7d["count"]) in f.observation.text


def test_coverage_finding_lists_exclusions(sample_metrics_and_findings) -> None:
    _, findings, _ = sample_metrics_and_findings
    f = _by_id(findings)["F-COVERAGE"]

    assert f.strength == "info"
    assert f.status == "supported"
    assert "duplicate_ticket_id" in f.observation.text
    assert "unknown_category" in f.observation.text


def test_finding_marked_insufficient_data_below_min_sample() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 9, 20, 12, 0, 0, tzinfo=IST)
    # Only 5 rows -> below min_sample (30)
    records = [
        {
            "row_id": i + 1,
            "ticket_id": f"KL-{i}",
            "created_at": "2026-09-10T10:00:00+05:30",
            "assigned_at": "2026-09-10T13:00:00+05:30",
            "first_response_at": "2026-09-10T14:00:00+05:30",
            "resolved_at": "2026-09-11T10:00:00+05:30",
            "category": "order_tracking",
            "priority": "medium",
            "queue": "Order support",
            "assigned_agent": "Agent 01",
            "status": "resolved",
            "channel": "email",
            "reassignment_count": 0,
            "customer_id": f"CUST-{i}",
            "is_valid": True,
            "validation_flags": [],
        }
        for i in range(5)
    ]
    frame = build_ticket_frame(records, config)
    results = compute_all_metrics(frame, config, as_of=as_of)
    findings = generate_findings(results, config)

    triage = _by_id(findings)["F-TRIAGE"]
    assert triage.status == "insufficient_data"
    assert triage.strength is None
    assert "Not enough data to assess" in triage.observation.text


def test_every_finding_has_observation_hypothesis_evidence_limitations_and_questions(
    sample_metrics_and_findings,
) -> None:
    _, findings, _ = sample_metrics_and_findings
    assert len(findings) >= 5

    for f in findings:
        assert f.observation.type == "observed_fact"
        assert f.observation.text.strip() != ""
        assert f.hypothesis.type == "hypothesis"
        assert f.hypothesis.text.strip() != ""
        assert len(f.evidence) >= 1
        assert len(f.limitations) >= 1
        assert len(f.validation_questions) >= 1
        assert all(q.kind == "template_question" for q in f.validation_questions)


def test_observation_text_never_contains_causal_wording(
    sample_metrics_and_findings,
) -> None:
    _, findings, _ = sample_metrics_and_findings

    for f in findings:
        obs = f.observation.text.lower()
        for pattern in BANNED_CAUSAL_PHRASES:
            assert re.search(pattern, obs) is None, (
                f"Finding {f.id} observation used banned causal wording matching {pattern}: {f.observation.text}"
            )


def test_hypothesis_text_is_hedged(sample_metrics_and_findings) -> None:
    _, findings, _ = sample_metrics_and_findings

    for f in findings:
        hyp = f.hypothesis.text.lower()
        assert any(re.search(pattern, hyp) for pattern in HEDGING_WORDS), (
            f"Finding {f.id} hypothesis lacks hedging: {f.hypothesis.text}"
        )


def test_every_evidence_value_matches_the_referenced_metric_result(
    sample_metrics_and_findings,
) -> None:
    results, findings, _ = sample_metrics_and_findings

    for f in findings:
        for ev in f.evidence:
            metric = results[ev.metric_id]
            if ev.metric_id == "triage_share_of_first_response":
                assert ev.value == pytest.approx(metric.data["share"])
            elif ev.metric_id == "triage_time":
                if ev.params.get("field") == "n_excluded":
                    assert ev.value == metric.n_excluded
                else:
                    assert ev.value == pytest.approx(metric.data["median"])
            elif ev.metric_id == "reassignment_rate":
                if "category" in ev.params:
                    row = next(
                        r for r in metric.data["by_category"] if r["category"] == ev.params["category"]
                    )
                    assert ev.value == pytest.approx(row["rate"])
                else:
                    assert ev.value == pytest.approx(metric.data["overall"]["rate"])
            elif ev.metric_id == "first_response_by_band":
                row = next(r for r in metric.data if r["band"] == ev.params["band"])
                assert ev.value == pytest.approx(row["median"])
            elif ev.metric_id == "agent_workload":
                assert ev.value == pytest.approx(metric.data["top_n_share"])
            elif ev.metric_id == "factor_comparison":
                row = next(
                    r for r in metric.data if r["factor_id"] == ev.params["factor_id"]
                )
                assert ev.value == pytest.approx(row["difference_hours"])
            elif ev.metric_id == "backlog_ageing":
                bucket = next(
                    b for b in metric.data["buckets"] if b["bucket"] == ev.params["bucket"]
                )
                if ev.params.get("field") == "share":
                    assert ev.value == pytest.approx(bucket["share"])
                else:
                    assert ev.value == bucket["count"]
            elif ev.metric_id in ("first_response_time", "resolution_time"):
                assert ev.params.get("field") == "n_excluded"
                assert ev.value == metric.n_excluded


def test_findings_are_deterministic(sample_metrics_and_findings) -> None:
    results, findings, config = sample_metrics_and_findings
    second = generate_findings(results, config)

    assert [f.model_dump() for f in findings] == [f.model_dump() for f in second]
