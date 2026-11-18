"""Unit tests for deterministic operational metrics with hand-computed expectations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.metrics.config import load_metrics_config
from app.metrics.frame import build_ticket_frame, scope
from app.metrics.registry import METRIC_REGISTRY, compute_all_metrics, compute_metric
from app.metrics.stats import describe_hours, gini_coefficient

REPO_ROOT = Path(__file__).resolve().parents[2]
IST = timezone(timedelta(hours=5, minutes=30))


def _row(
    ticket_id: str,
    created: str,
    *,
    assigned: str | None = None,
    first_response: str | None = None,
    resolved: str | None = None,
    category: str = "order_tracking",
    priority: str = "medium",
    queue: str = "Order support",
    assigned_agent: str | None = "Agent 01",
    status: str = "resolved",
    channel: str = "email",
    reassignment_count: Any = 0,
    customer_id: str = "CUST-1",
    validation_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    flags = validation_flags or []
    is_valid = not any("all_metrics" in f.get("affects", []) for f in flags)
    return {
        "row_id": 1,
        "ticket_id": ticket_id,
        "created_at": created,
        "assigned_at": assigned,
        "first_response_at": first_response,
        "resolved_at": resolved,
        "category": category,
        "priority": priority,
        "queue": queue,
        "assigned_agent": assigned_agent,
        "status": status,
        "channel": channel,
        "reassignment_count": reassignment_count,
        "customer_id": customer_id,
        "is_valid": is_valid,
        "validation_flags": flags,
    }


def test_describe_hours_median_p90_mean_and_n() -> None:
    # Hand calculation for [1, 2, 3, 4, 10]:
    # n = 5
    # median (50th linear) = 3.0
    # p90 (linear index = 0.9 * 4 = 3.6 -> 4 + 0.6*(10-4) = 7.6)
    # mean = (1+2+3+4+10)/5 = 4.0
    result = describe_hours([1.0, 2.0, 3.0, 4.0, 10.0])

    assert result["n"] == 5
    assert result["median"] == pytest.approx(3.0)
    assert result["p90"] == pytest.approx(7.6)
    assert result["mean"] == pytest.approx(4.0)


def test_describe_hours_empty_returns_nulls_and_zero_n() -> None:
    assert describe_hours([]) == {"n": 0, "median": None, "p90": None, "mean": None}


def test_describe_hours_single_value() -> None:
    assert describe_hours([5.5]) == {"n": 1, "median": 5.5, "p90": 5.5, "mean": 5.5}


def test_frame_converts_to_ist_and_applies_scope_masks() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            # 19:00 UTC on Sep 10 -> 00:30 IST on Sep 11 (overnight band)
            _row("T1", "2026-09-10T19:00:00Z"),
            _row(
                "T2",
                "2026-09-10T05:00:00Z",  # 10:30 IST -> morning band
                validation_flags=[{"code": "first_response_before_created", "affects": ["response_metrics"]}],
            ),
        ],
        config,
    )

    assert list(frame["created_date_ist"]) == ["2026-09-11", "2026-09-10"]
    assert list(frame["creation_band"]) == ["overnight", "morning"]

    all_df, all_info = scope(frame, "all")
    resp_df, resp_info = scope(frame, "response")
    assert len(all_df) == 2 and all_info.n_excluded == 0
    assert len(resp_df) == 1 and resp_info.n_excluded == 1


def test_scope_exclusions_reported_by_flag_code() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30"),
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                validation_flags=[{"code": "duplicate_ticket_id", "affects": ["all_metrics"]}],
            ),
            _row(
                "T3",
                "2026-09-10T10:00:00+05:30",
                validation_flags=[
                    {"code": "missing_first_response_on_resolved", "affects": ["response_metrics"]}
                ],
            ),
        ],
        config,
    )

    _, resp_info = scope(frame, "response")
    assert resp_info.n_included == 1
    assert resp_info.n_excluded == 2
    assert resp_info.exclusions_by_flag_code == {
        "duplicate_ticket_id": 1,
        "missing_first_response_on_resolved": 1,
    }


def test_first_response_time_hand_computed() -> None:
    config = load_metrics_config()
    # Durations: T1=2h, T2=4h, T3=6h -> median=4.0, mean=4.0, p90=4 + 0.8*2 = 5.6
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T12:00:00+05:30"),
            _row("T2", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T14:00:00+05:30"),
            _row("T3", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T16:00:00+05:30"),
        ],
        config,
    )
    res = compute_metric("first_response_time", frame, config)

    assert res.data["n"] == 3
    assert res.data["median"] == pytest.approx(4.0)
    assert res.data["mean"] == pytest.approx(4.0)
    assert res.data["p90"] == pytest.approx(5.6)
    assert res.data["unanswered_count"] == 0


def test_first_response_reports_unanswered_separately() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T13:00:00+05:30"),
            _row("T2", "2026-09-10T10:00:00+05:30", status="open", first_response=None),
        ],
        config,
    )
    res = compute_metric("first_response_time", frame, config)

    assert res.data["n"] == 1
    assert res.data["median"] == pytest.approx(3.0)
    assert res.data["unanswered_count"] == 1


def test_first_response_excludes_response_flagged_rows() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T12:00:00+05:30"),
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                first_response="2026-09-10T09:00:00+05:30",
                validation_flags=[{"code": "first_response_before_created", "affects": ["response_metrics"]}],
            ),
        ],
        config,
    )
    res = compute_metric("first_response_time", frame, config)

    assert res.n_included == 1
    assert res.n_excluded == 1
    assert res.exclusions == {"first_response_before_created": 1}
    assert res.data["median"] == pytest.approx(2.0)


def test_triage_time_hand_computed() -> None:
    config = load_metrics_config()
    # Triage lags: 1h and 5h -> median=3.0, mean=3.0
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", assigned="2026-09-10T11:00:00+05:30"),
            _row("T2", "2026-09-10T10:00:00+05:30", assigned="2026-09-10T15:00:00+05:30"),
        ],
        config,
    )
    res = compute_metric("triage_time", frame, config)

    assert res.data["n"] == 2
    assert res.data["median"] == pytest.approx(3.0)
    assert res.data["mean"] == pytest.approx(3.0)


def test_agent_response_time_hand_computed() -> None:
    config = load_metrics_config()
    # Agent lags (first_response - assigned): 1.5h and 2.5h -> median=2.0, mean=2.0
    frame = build_ticket_frame(
        [
            _row(
                "T1",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T12:00:00+05:30",
                first_response="2026-09-10T13:30:00+05:30",
            ),
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T12:00:00+05:30",
                first_response="2026-09-10T14:30:00+05:30",
            ),
        ],
        config,
    )
    res = compute_metric("agent_response_time", frame, config)

    assert res.scope == "response+triage"
    assert res.data["n"] == 2
    assert res.data["median"] == pytest.approx(2.0)
    assert res.data["mean"] == pytest.approx(2.0)


def test_triage_share_aggregate_definition() -> None:
    config = load_metrics_config()
    # T1: triage=3h, frt=4h; T2: triage=3h, frt=6h
    # Aggregate ratio = (3+3) / (4+6) = 6 / 10 = 0.60 (not average of 0.75 and 0.50 = 0.625)
    frame = build_ticket_frame(
        [
            _row(
                "T1",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T13:00:00+05:30",
                first_response="2026-09-10T14:00:00+05:30",
            ),
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T13:00:00+05:30",
                first_response="2026-09-10T16:00:00+05:30",
            ),
        ],
        config,
    )
    res = compute_metric("triage_share_of_first_response", frame, config)

    assert res.data["n"] == 2
    assert res.data["triage_hours_sum"] == pytest.approx(6.0)
    assert res.data["first_response_hours_sum"] == pytest.approx(10.0)
    assert res.data["share"] == pytest.approx(0.60)


def test_resolution_time_excludes_unresolved_and_reports_count() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", resolved="2026-09-10T20:00:00+05:30", status="resolved"),
            _row("T2", "2026-09-10T10:00:00+05:30", resolved=None, status="open"),
            _row("T3", "2026-09-10T10:00:00+05:30", resolved=None, status="pending"),
        ],
        config,
    )
    res = compute_metric("resolution_time", frame, config)

    assert res.data["n"] == 1
    assert res.data["median"] == pytest.approx(10.0)
    assert res.data["unresolved_count"] == 2


def test_volume_by_day_uses_ist_dates() -> None:
    config = load_metrics_config()
    # 19:00 UTC on 2026-09-10 is 00:30 IST on 2026-09-11
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T19:00:00Z"),
            _row("T2", "2026-09-10T10:00:00Z"),
        ],
        config,
    )
    res = compute_metric("volume_by_day", frame, config)

    assert [(r["date"], r["count"]) for r in res.data] == [
        ("2026-09-10", 1),
        ("2026-09-11", 1),
    ]


def test_volume_by_hour_and_band_assignment_including_overnight_wrap() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T09:15:00+05:30"),  # morning
            _row("T2", "2026-09-10T14:00:00+05:30"),  # afternoon
            _row("T3", "2026-09-10T21:59:00+05:30"),  # evening
            _row("T4", "2026-09-10T22:00:00+05:30"),  # overnight (late)
            _row("T5", "2026-09-11T08:59:00+05:30"),  # overnight (early wrap)
        ],
        config,
    )
    by_hour = compute_metric("volume_by_hour", frame, config)
    by_band = compute_metric("volume_by_band", frame, config)

    hour_counts = {r["hour"]: r["count"] for r in by_hour.data}
    assert hour_counts[9] == 1 and hour_counts[22] == 1 and hour_counts[8] == 1

    band_counts = {r["band"]: r["count"] for r in by_band.data}
    assert band_counts == {"morning": 1, "afternoon": 1, "evening": 1, "overnight": 2}


def test_volume_by_category_and_channel_counts_and_shares() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", category="order_tracking", channel="email"),
            _row("T2", "2026-09-10T10:00:00+05:30", category="order_tracking", channel="email"),
            _row("T3", "2026-09-10T10:00:00+05:30", category="returns_refunds", channel="chat"),
            _row("T4", "2026-09-10T10:00:00+05:30", category="returns_refunds", channel="custom_bot"),
        ],
        config,
    )
    cats = compute_metric("volume_by_category", frame, config)
    chans = compute_metric("volume_by_channel", frame, config)

    assert {r["category"]: (r["count"], r["share"]) for r in cats.data} == {
        "order_tracking": (2, 0.5),
        "returns_refunds": (2, 0.5),
    }
    assert {r["channel"]: (r["count"], r["share"]) for r in chans.data} == {
        "email": (2, 0.5),
        "chat": (1, 0.25),
        "unknown": (1, 0.25),
    }


def test_backlog_counts_by_ageing_bucket_as_of_period_end() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    frame = build_ticket_frame(
        [
            _row("T1", "2026-10-10T06:00:00Z", status="open"),      # 0.25d -> lt_1d
            _row("T2", "2026-10-08T12:00:00Z", status="pending"),   # 2.0d  -> d1_3
            _row("T3", "2026-10-05T12:00:00Z", status="open"),      # 5.0d  -> d3_7
            _row("T4", "2026-09-30T12:00:00Z", status="pending"),   # 10.0d -> gte_7d
            _row("T5", "2026-09-20T12:00:00Z", status="resolved"),  # ignored (resolved)
        ],
        config,
    )
    res = compute_metric("backlog_ageing", frame, config, as_of=as_of)

    assert res.data["total_open_backlog"] == 4
    assert res.data["oldest_age_days"] == pytest.approx(10.0)
    buckets = {b["bucket"]: b["count"] for b in res.data["buckets"]}
    assert buckets == {"lt_1d": 1, "d1_3": 1, "d3_7": 1, "gte_7d": 1}


def test_backlog_bucket_boundaries() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
    # Exact boundary ages: 0.0d -> lt_1d, 1.0d -> d1_3, 3.0d -> d3_7, 7.0d -> gte_7d
    frame = build_ticket_frame(
        [
            _row("B0", "2026-10-10T00:00:00Z", status="open"),
            _row("B1", "2026-10-09T00:00:00Z", status="open"),
            _row("B3", "2026-10-07T00:00:00Z", status="open"),
            _row("B7", "2026-10-03T00:00:00Z", status="open"),
        ],
        config,
    )
    res = compute_metric("backlog_ageing", frame, config, as_of=as_of)
    buckets = {b["bucket"]: b["count"] for b in res.data["buckets"]}
    assert buckets == {"lt_1d": 1, "d1_3": 1, "d3_7": 1, "gte_7d": 1}


def test_agent_workload_shares_and_top_n() -> None:
    config = load_metrics_config()
    rows = (
        [_row(f"A1-{i}", "2026-09-10T10:00:00+05:30", assigned_agent="Agent 01") for i in range(4)]
        + [_row(f"A2-{i}", "2026-09-10T10:00:00+05:30", assigned_agent="Agent 02") for i in range(3)]
        + [_row(f"A3-{i}", "2026-09-10T10:00:00+05:30", assigned_agent="Agent 03") for i in range(2)]
        + [_row("A4-0", "2026-09-10T10:00:00+05:30", assigned_agent="Agent 04")]
        + [_row("UN-0", "2026-09-10T10:00:00+05:30", assigned_agent=None)]
    )
    frame = build_ticket_frame(rows, config)
    res = compute_metric("agent_workload", frame, config)

    # Assigned total = 10, top 3 = 4+3+2 = 9 -> 0.90, unassigned = 1
    assert res.data["assigned_total"] == 10
    assert res.data["unassigned_count"] == 1
    assert res.data["top_n_agents"] == ["Agent 01", "Agent 02", "Agent 03"]
    assert res.data["top_n_share"] == pytest.approx(0.90)


def test_gini_known_values() -> None:
    assert gini_coefficient([10, 10, 10, 10]) == pytest.approx(0.0)
    # 1 agent holds everything among n=5 -> (5-1)/5 = 0.8
    assert gini_coefficient([100, 0, 0, 0, 0]) == pytest.approx(0.8)
    assert gini_coefficient([]) is None


def test_reassignment_rate_by_category_and_overall() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", category="order_tracking", queue="Order support", reassignment_count=2),
            _row("T2", "2026-09-10T10:00:00+05:30", category="order_tracking", queue="Order support", reassignment_count=0),
            _row("T3", "2026-09-10T10:00:00+05:30", category="payment_issues", queue="Payments", reassignment_count=0),
            _row("T4", "2026-09-10T10:00:00+05:30", category="payment_issues", queue="Payments", reassignment_count=0),
        ],
        config,
    )
    res = compute_metric("reassignment_rate", frame, config)

    # Overall: 1 of 4 reassigned (0.25), mean = 2/4 = 0.5
    assert res.data["overall"]["rate"] == pytest.approx(0.25)
    assert res.data["overall"]["mean_reassignments"] == pytest.approx(0.5)
    by_cat = {r["category"]: r["rate"] for r in res.data["by_category"]}
    assert by_cat == {"order_tracking": 0.5, "payment_issues": 0.0}


def test_reassignment_count_unusable_values_excluded_and_counted() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", reassignment_count=1),
            _row("T2", "2026-09-10T10:00:00+05:30", reassignment_count=""),
            _row("T3", "2026-09-10T10:00:00+05:30", reassignment_count="abc"),
            _row("T4", "2026-09-10T10:00:00+05:30", reassignment_count=None),
        ],
        config,
    )
    res = compute_metric("reassignment_rate", frame, config)

    assert res.n_included == 1
    assert res.n_excluded == 3
    assert res.exclusions["reassignment_count_unusable"] == 3
    assert res.data["overall"]["rate"] == pytest.approx(1.0)


def test_reassigned_vs_not_comparison() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T16:00:00+05:30", reassignment_count=1),  # 6h
            _row("T2", "2026-09-10T10:00:00+05:30", first_response="2026-09-10T12:00:00+05:30", reassignment_count=0),  # 2h
        ],
        config,
    )
    res = compute_metric("reassigned_vs_not", frame, config)

    assert res.data["reassigned"]["median"] == pytest.approx(6.0)
    assert res.data["not_reassigned"]["median"] == pytest.approx(2.0)
    assert res.data["median_difference_hours"] == pytest.approx(4.0)


def test_sla_attainment_among_responded_and_unanswered_past_threshold() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 9, 15, 10, 0, 0, tzinfo=IST)
    # FRT threshold = 4h; Res threshold = 72h
    frame = build_ticket_frame(
        [
            # Responded in 2h (met), resolved in 24h (met)
            _row(
                "T1",
                "2026-09-10T10:00:00+05:30",
                first_response="2026-09-10T12:00:00+05:30",
                resolved="2026-09-11T10:00:00+05:30",
                status="resolved",
            ),
            # Responded in 6h (missed), resolved in 96h (missed)
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                first_response="2026-09-10T16:00:00+05:30",
                resolved="2026-09-14T10:00:00+05:30",
                status="resolved",
            ),
            # Unanswered open ticket created 5 days before as_of (>4h and >72h)
            _row(
                "T3",
                "2026-09-10T10:00:00+05:30",
                first_response=None,
                resolved=None,
                status="open",
            ),
            # Unanswered open ticket created 1h before as_of (<=4h and <=72h)
            _row(
                "T4",
                "2026-09-15T09:00:00+05:30",
                first_response=None,
                resolved=None,
                status="open",
            ),
        ],
        config,
    )
    res = compute_metric("sla_attainment", frame, config, as_of=as_of)

    assert res.data["first_response"]["responded_n"] == 2
    assert res.data["first_response"]["attainment_rate"] == pytest.approx(0.5)
    assert res.data["first_response"]["unanswered_past_threshold_count"] == 1
    assert res.data["resolution"]["resolved_n"] == 2
    assert res.data["resolution"]["attainment_rate"] == pytest.approx(0.5)
    assert res.data["resolution"]["unresolved_past_threshold_count"] == 1
    assert any("not agreed with the client" in note.lower() for note in res.notes)


def test_category_delay_table_hand_computed() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row(
                "T1",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T12:00:00+05:30",      # 2h
                first_response="2026-09-10T14:00:00+05:30",  # 4h
                resolved="2026-09-10T20:00:00+05:30",      # 10h
                category="order_tracking",
                reassignment_count=1,
            ),
            _row(
                "T2",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T14:00:00+05:30",      # 4h
                first_response="2026-09-10T16:00:00+05:30",  # 6h
                resolved="2026-09-10T22:00:00+05:30",      # 12h
                category="order_tracking",
                reassignment_count=0,
            ),
        ],
        config,
    )
    res = compute_metric("category_delay_table", frame, config)

    assert len(res.data) == 1
    row = res.data[0]
    assert row["category"] == "order_tracking"
    assert row["n"] == 2
    assert row["median_triage_hours"] == pytest.approx(3.0)
    assert row["median_first_response_hours"] == pytest.approx(5.0)
    assert row["median_resolution_hours"] == pytest.approx(11.0)
    assert row["reassignment_rate"] == pytest.approx(0.5)


def test_first_response_by_band() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("A1", "2026-09-10T15:00:00+05:30", first_response="2026-09-10T17:00:00+05:30"),  # afternoon: 2h
            _row("E1", "2026-09-10T19:00:00+05:30", first_response="2026-09-11T00:00:00+05:30"),  # evening: 5h
        ],
        config,
    )
    res = compute_metric("first_response_by_band", frame, config)
    by_band = {r["band"]: r for r in res.data}

    assert by_band["afternoon"]["median"] == pytest.approx(2.0)
    assert by_band["evening"]["median"] == pytest.approx(5.0)
    assert by_band["morning"]["n"] == 0


def test_factor_comparison_rows_carry_n_difference_and_non_causal_note() -> None:
    config = load_metrics_config()
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T15:00:00+05:30", assigned="2026-09-10T16:00:00+05:30", first_response="2026-09-10T17:00:00+05:30", reassignment_count=0, assigned_agent="Agent 01"),
            _row("T2", "2026-09-10T19:00:00+05:30", assigned="2026-09-10T21:00:00+05:30", first_response="2026-09-11T00:00:00+05:30", reassignment_count=1, assigned_agent="Agent 04"),
        ],
        config,
    )
    res = compute_metric("factor_comparison", frame, config)

    assert len(res.data) == 4
    for item in res.data:
        assert "group_a_n" in item and "group_b_n" in item
        assert "difference_hours" in item
        assert "Observed association only" in item["note"]
        assert "not an estimate of effect" in item["note"]


def test_every_metric_result_has_definition_scope_exclusions_params_and_as_of() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    frame = build_ticket_frame(
        [
            _row(
                "T1",
                "2026-09-10T10:00:00+05:30",
                assigned="2026-09-10T12:00:00+05:30",
                first_response="2026-09-10T13:00:00+05:30",
                resolved="2026-09-11T10:00:00+05:30",
            )
        ],
        config,
    )
    results = compute_all_metrics(frame, config, as_of=as_of)

    assert set(results.keys()) == set(METRIC_REGISTRY.keys())
    for metric_id, res in results.items():
        assert res.metric_id == metric_id
        assert res.definition.strip() != ""
        assert res.scope.strip() != ""
        assert isinstance(res.exclusions, dict)
        assert isinstance(res.params, dict)
        assert res.as_of == as_of


def test_empty_valid_set_returns_empty_results_without_error() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    frame = build_ticket_frame(
        [
            _row(
                "BAD-1",
                "2026-09-10T10:00:00+05:30",
                category="billing_misc",
                validation_flags=[{"code": "unknown_category", "affects": ["all_metrics"]}],
            )
        ],
        config,
    )
    results = compute_all_metrics(frame, config, as_of=as_of)

    assert results["first_response_time"].data["n"] == 0
    assert results["first_response_time"].data["median"] is None
    assert results["triage_share_of_first_response"].data["share"] is None
    assert results["backlog_ageing"].data["total_open_backlog"] == 0
    assert results["agent_workload"].data["gini"] is None
    assert results["reassignment_rate"].data["overall"]["rate"] is None


def test_metrics_are_deterministic_for_repeated_calls() -> None:
    config = load_metrics_config()
    as_of = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    frame = build_ticket_frame(
        [
            _row("T1", "2026-09-10T10:00:00+05:30", assigned="2026-09-10T12:00:00+05:30", first_response="2026-09-10T14:00:00+05:30", resolved="2026-09-11T10:00:00+05:30"),
            _row("T2", "2026-09-10T19:00:00+05:30", assigned="2026-09-10T22:00:00+05:30", first_response="2026-09-11T01:00:00+05:30", resolved="2026-09-12T10:00:00+05:30", reassignment_count=1),
        ],
        config,
    )
    first = {k: v.model_dump() for k, v in compute_all_metrics(frame, config, as_of).items()}
    second = {k: v.model_dump() for k, v in compute_all_metrics(frame, config, as_of).items()}

    assert first == second


def test_metrics_config_rejects_overlapping_bands_and_nonpositive_sla(tmp_path: Path) -> None:
    base = yaml.safe_load((REPO_ROOT / "config" / "metrics.yaml").read_text(encoding="utf-8"))

    overlapping = dict(base)
    overlapping["creation_bands"] = {
        "morning": {"start": 9, "end": 15},
        "afternoon": {"start": 14, "end": 18},
        "evening": {"start": 18, "end": 22},
        "overnight": {"start": 22, "end": 9},
    }
    (tmp_path / "metrics.yaml").write_text(yaml.safe_dump(overlapping), encoding="utf-8")
    with pytest.raises(ValidationError, match="Overlapping creation_bands"):
        load_metrics_config(tmp_path)

    bad_sla = dict(base)
    bad_sla["sla"] = {"first_response_hours": 0, "resolution_hours": 72}
    (tmp_path / "metrics.yaml").write_text(yaml.safe_dump(bad_sla), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_metrics_config(tmp_path)


def test_metrics_and_findings_code_never_reference_llm_or_answer_key() -> None:
    targets = [
        REPO_ROOT / "backend" / "app" / "metrics",
        REPO_ROOT / "backend" / "app" / "findings",
    ]
    violations: list[str] = []
    for folder in targets:
        for py_file in folder.rglob("*.py"):
            lowered = py_file.read_text(encoding="utf-8").lower()
            if "llm" in lowered or "answer_key" in lowered:
                violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert violations == []
