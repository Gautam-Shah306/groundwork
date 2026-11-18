"""Deterministic synthetic dataset generator for Groundwork (Kora Living).

Generates three files under data/ using fixed seed 42:
  - data/sample_tickets.csv  (2,000 operational support tickets over 8 weeks)
  - data/eval_tickets.json   (150 varied ground-truth triage evaluation tickets)
  - data/answer_key.json     (planted causes, exact injected issues, measured effects)

Run natively from repo root or backend/:
    backend\\.venv\\Scripts\\python.exe scripts/generate_data.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.triage.config import TriageConfig, load_triage_config  # noqa: E402
from app.triage.priority import evaluate_priority  # noqa: E402
from eval_templates import (  # noqa: E402
    AMBIGUOUS_TICKETS,
    CATEGORY_TEMPLATES,
    CHANNELS,
    CITIES,
    DATES,
    HINGLISH_TICKETS,
    PRODUCTS,
    SHORT_TICKETS,
)

SEED = 42
IST = timezone(timedelta(hours=5, minutes=30))
PERIOD_START = datetime(2026, 9, 7, 0, 0, 0, tzinfo=IST)  # Monday
PERIOD_END = datetime(2026, 11, 1, 23, 59, 59, tzinfo=IST)  # Sunday (8 weeks)
NUM_DAYS = 56

BASE_TICKET_COUNT = 1997  # + 3 duplicate ticket_id rows = 2,000 rows total
INJECTED_COUNTS = {
    "resolved_missing_first_response_at": 12,
    "duplicate_ticket_ids": 3,
    "first_response_before_created": 8,
    "unknown_category_billing_misc": 6,
    "resolved_missing_resolved_at": 9,
    "resolved_over_300_days": 4,
}

CSV_COLUMNS = [
    "ticket_id",
    "created_at",
    "assigned_at",
    "first_response_at",
    "resolved_at",
    "category",
    "priority",
    "queue",
    "assigned_agent",
    "status",
    "channel",
    "reassignment_count",
    "customer_id",
]

CATEGORY_WEIGHTS = [
    ("order_tracking", 0.30),
    ("returns_refunds", 0.22),
    ("product_questions", 0.14),
    ("payment_issues", 0.12),
    ("address_change", 0.08),
    ("damaged_item", 0.08),
    ("account_login", 0.06),
]

CHANNEL_WEIGHTS = [
    ("email", 0.42),
    ("web_form", 0.24),
    ("chat", 0.18),
    ("whatsapp", 0.16),
]

DAY_AGENTS = [f"Agent {i:02d}" for i in range(1, 10)]  # Agent 01..09 (09:00-18:00)
LATE_AGENTS = [f"Agent {i:02d}" for i in range(10, 13)]  # Agent 10..12 (14:00-22:00)
TOP_THREE_AGENTS = {"Agent 01", "Agent 02", "Agent 03"}


def _format_ts(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(IST).isoformat(timespec="seconds")


def _sample_creation_timestamps(rng: np.random.Generator, count: int) -> list[datetime]:
    # Weekday weights: Mon-Fri higher, Sat-Sun moderate
    weekday_weights = np.array([1.22, 1.18, 1.12, 1.08, 1.14, 0.72, 0.64], dtype=float)
    day_weights = np.array(
        [weekday_weights[(PERIOD_START + timedelta(days=d)).weekday()] for d in range(NUM_DAYS)],
        dtype=float,
    )
    day_probs = day_weights / day_weights.sum()

    # Hourly profile (IST 00..23): peaks late morning (10-13) and evening (18-21)
    hour_weights = np.array(
        [
            0.010, 0.008, 0.006, 0.006, 0.007, 0.010,
            0.016, 0.024, 0.038, 0.056, 0.082, 0.094,
            0.090, 0.072, 0.058, 0.056, 0.054, 0.056,
            0.068, 0.074, 0.056, 0.032, 0.016, 0.011,
        ],
        dtype=float,
    )
    hour_probs = hour_weights / hour_weights.sum()

    days = rng.choice(NUM_DAYS, size=count, p=day_probs)
    hours = rng.choice(24, size=count, p=hour_probs)
    minutes = rng.integers(0, 60, size=count)
    seconds = rng.integers(0, 60, size=count)

    timestamps = [
        PERIOD_START + timedelta(days=int(d), hours=int(h), minutes=int(m), seconds=int(s))
        for d, h, m, s in zip(days, hours, minutes, seconds)
    ]
    timestamps.sort()
    return timestamps


def _next_shift_start(created_at: datetime) -> datetime:
    """Return effective staffed start time in IST (overnight 22:00-09:00 waits for 09:00)."""
    hour = created_at.hour
    if 9 <= hour < 22:
        return created_at
    if hour >= 22:
        next_day = (created_at + timedelta(days=1)).date()
        return datetime(next_day.year, next_day.month, next_day.day, 9, 0, 0, tzinfo=IST)
    same_day = created_at.date()
    return datetime(same_day.year, same_day.month, same_day.day, 9, 0, 0, tzinfo=IST)


def _choose_agent(rng: np.random.Generator, created_hour: int) -> str:
    """Assign agent respecting shift coverage and mild top-3 workload skew (~40% total)."""
    if 18 <= created_hour < 22:
        return str(rng.choice(LATE_AGENTS, p=[0.36, 0.34, 0.30]))

    # Day + overnight tickets (~77% of volume): Agent 01..03 get ~51% so overall share is ~40%
    if 14 <= created_hour < 18:
        # Both shifts staffed; slight share to late agents as well
        pool = DAY_AGENTS + LATE_AGENTS
        weights = np.array(
            [0.165, 0.160, 0.155, 0.060, 0.060, 0.058, 0.058, 0.056, 0.056, 0.058, 0.057, 0.057],
            dtype=float,
        )
        weights /= weights.sum()
        return str(rng.choice(pool, p=weights))

    # Morning (09-14) and overnight queue worked at 09:00 by day shift (Agent 01..09)
    day_weights = np.array(
        [0.184, 0.178, 0.172, 0.080, 0.079, 0.078, 0.077, 0.076, 0.076],
        dtype=float,
    )
    day_weights /= day_weights.sum()
    return str(rng.choice(DAY_AGENTS, p=day_weights))


def _generate_sample_tickets(
    rng: np.random.Generator,
    triage_config: TriageConfig,
) -> list[dict[str, Any]]:
    cat_ids = [c for c, _ in CATEGORY_WEIGHTS]
    cat_probs = [w for _, w in CATEGORY_WEIGHTS]
    chan_ids = [c for c, _ in CHANNEL_WEIGHTS]
    chan_probs = [w for _, w in CHANNEL_WEIGHTS]
    cat_to_queue = triage_config.category_to_queue

    # Pool of 1,300 distinct customers with realistic repeat frequency
    customer_pool = [f"CUST-{i:04d}" for i in range(1, 1301)]
    # Guarantee ~1,250-1,300 distinct customer IDs by sampling without replacement first
    # for 1,280 rows and with replacement for remaining rows.
    first_pass = rng.choice(customer_pool, size=1280, replace=False)
    repeat_pass = rng.choice(customer_pool[:420], size=BASE_TICKET_COUNT - 1280, replace=True)
    customer_ids = np.concatenate([first_pass, repeat_pass])
    rng.shuffle(customer_ids)

    timestamps = _sample_creation_timestamps(rng, BASE_TICKET_COUNT)
    categories = rng.choice(cat_ids, size=BASE_TICKET_COUNT, p=cat_probs)
    channels = rng.choice(chan_ids, size=BASE_TICKET_COUNT, p=chan_probs)
    priorities = rng.choice(["low", "medium", "high"], size=BASE_TICKET_COUNT, p=[0.50, 0.35, 0.15])

    # Status mix: ~88% resolved, ~7% pending, ~5% open.
    # Ensure most open/pending tickets are older than 3 days before PERIOD_END.
    cutoff_3d = PERIOD_END - timedelta(days=3)
    statuses: list[str] = []
    for ts in timestamps:
        if ts < cutoff_3d:
            st = str(rng.choice(["resolved", "pending", "open"], p=[0.875, 0.073, 0.052]))
        else:
            st = str(rng.choice(["resolved", "pending", "open"], p=[0.93, 0.04, 0.03]))
        statuses.append(st)

    rows: list[dict[str, Any]] = []
    for idx in range(BASE_TICKET_COUNT):
        ticket_id = f"KL-{idx + 1:06d}"
        created_at = timestamps[idx]
        category = str(categories[idx])
        channel = str(channels[idx])
        priority = str(priorities[idx])
        status = statuses[idx]
        customer_id = str(customer_ids[idx])
        created_hour = created_at.hour

        agent = _choose_agent(rng, created_hour)
        effective_start = _next_shift_start(created_at)

        # Planted cause 1: Slow manual triage (dominant: ~3-4h median staffed, ~55-65% of FRT)
        if 18 <= created_hour < 22:
            # Planted cause 3: Evening coverage gap (only 3 late-shift agents)
            triage_hours = float(rng.lognormal(mean=math.log(4.40), sigma=0.42))
        elif 14 <= created_hour < 18:
            # Peak staffing overlap (12 agents)
            triage_hours = float(rng.lognormal(mean=math.log(2.80), sigma=0.38))
        elif 9 <= created_hour < 14:
            triage_hours = float(rng.lognormal(mean=math.log(3.25), sigma=0.42))
        else:
            # Overnight tickets wait for 09:00 shift start, then enter morning manual triage
            triage_hours = float(rng.lognormal(mean=math.log(3.10), sigma=0.40))

        triage_hours = max(0.35, min(triage_hours, 24.0))
        assigned_at = effective_start + timedelta(seconds=int(round(triage_hours * 3600)))

        # Planted cause 2: Misrouting between Order support and Returns and refunds (~35% vs ~8%)
        if category in ("order_tracking", "returns_refunds"):
            if rng.random() < 0.35:
                reassignment_count = 1 if rng.random() < 0.74 else 2
            else:
                reassignment_count = 0
        else:
            if rng.random() < 0.08:
                reassignment_count = 1 if rng.random() < 0.84 else 2
            else:
                reassignment_count = 0

        reassignment_hours = 0.0
        for _ in range(reassignment_count):
            reassignment_hours += float(np.clip(rng.lognormal(mean=math.log(1.85), sigma=0.32), 0.95, 3.35))

        # Queue: final queue after routing (occasionally misrouted queue remains on open tickets)
        queue = cat_to_queue[category]

        # Agent response lag: median ~1.3-1.6h in day, longer in evening, mild skew for top-3 agents
        if 18 <= created_hour < 22:
            agent_lag_hours = float(rng.lognormal(mean=math.log(2.25), sigma=0.40))
        elif 14 <= created_hour < 18:
            agent_lag_hours = float(rng.lognormal(mean=math.log(1.30), sigma=0.38))
        else:
            agent_lag_hours = float(rng.lognormal(mean=math.log(1.42), sigma=0.40))

        # Planted cause 4: Mild workload skew (weak effect on top-3 agents, << triage lag)
        if agent in TOP_THREE_AGENTS:
            agent_lag_hours += float(np.clip(rng.lognormal(mean=math.log(0.24), sigma=0.25), 0.08, 0.65))

        total_response_lag = max(0.15, min(agent_lag_hours + reassignment_hours, 28.0))
        first_response_at: datetime | None = assigned_at + timedelta(
            seconds=int(round(total_response_lag * 3600))
        )

        # Resolution time depends on category and reassignments
        category_res_median = {
            "order_tracking": 14.5,
            "returns_refunds": 22.0,
            "payment_issues": 18.0,
            "product_questions": 6.5,
            "address_change": 8.5,
            "damaged_item": 26.0,
            "account_login": 7.5,
        }[category]

        resolved_at: datetime | None
        if status == "resolved":
            extra_resolve_hours = float(
                np.clip(
                    rng.lognormal(mean=math.log(category_res_median), sigma=0.48)
                    + reassignment_count * 3.2,
                    0.5,
                    240.0,
                )
            )
            resolved_at = first_response_at + timedelta(seconds=int(round(extra_resolve_hours * 3600)))
        else:
            resolved_at = None

        rows.append(
            {
                "ticket_id": ticket_id,
                "created_at": _format_ts(created_at),
                "assigned_at": _format_ts(assigned_at),
                "first_response_at": _format_ts(first_response_at),
                "resolved_at": _format_ts(resolved_at),
                "category": category,
                "priority": priority,
                "queue": queue,
                "assigned_agent": agent,
                "status": status,
                "channel": channel,
                "reassignment_count": reassignment_count,
                "customer_id": customer_id,
            }
        )

    # Inject data-quality issues at EXACT counts on strictly disjoint rows.
    resolved_indices = [i for i, r in enumerate(rows) if r["status"] == "resolved"]
    rng.shuffle(resolved_indices)

    cursor = 0
    # 1. 12 resolved tickets with missing first_response_at
    missing_frt_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["resolved_missing_first_response_at"]]
    cursor += INJECTED_COUNTS["resolved_missing_first_response_at"]
    for i in missing_frt_idx:
        rows[i]["first_response_at"] = ""

    # 2. 8 tickets with first_response_at before created_at
    frt_before_created_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["first_response_before_created"]]
    cursor += INJECTED_COUNTS["first_response_before_created"]
    for i in frt_before_created_idx:
        created_dt = datetime.fromisoformat(rows[i]["created_at"])
        bad_dt = created_dt - timedelta(minutes=int(rng.integers(20, 95)))
        rows[i]["first_response_at"] = _format_ts(bad_dt)

    # 3. 6 tickets with unknown category value billing_misc
    unknown_cat_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["unknown_category_billing_misc"]]
    cursor += INJECTED_COUNTS["unknown_category_billing_misc"]
    for i in unknown_cat_idx:
        rows[i]["category"] = "billing_misc"

    # 4. 9 resolved tickets with missing resolved_at
    missing_res_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["resolved_missing_resolved_at"]]
    cursor += INJECTED_COUNTS["resolved_missing_resolved_at"]
    for i in missing_res_idx:
        rows[i]["resolved_at"] = ""

    # 5. 4 tickets with resolved_at more than 300 days after created_at
    over_300d_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["resolved_over_300_days"]]
    cursor += INJECTED_COUNTS["resolved_over_300_days"]
    for i in over_300d_idx:
        created_dt = datetime.fromisoformat(rows[i]["created_at"])
        bad_resolved = created_dt + timedelta(days=int(rng.integers(315, 385)))
        rows[i]["resolved_at"] = _format_ts(bad_resolved)

    # 6. 3 duplicate ticket_ids (copies of 3 clean valid rows)
    dup_source_idx = resolved_indices[cursor : cursor + INJECTED_COUNTS["duplicate_ticket_ids"]]
    for i in dup_source_idx:
        rows.append(dict(rows[i]))

    return rows


def _generate_eval_tickets(
    rng: np.random.Generator,
    triage_config: TriageConfig,
) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    seen_bodies: set[str] = set()
    order_seq = 81040

    def _next_order_id() -> str:
        nonlocal order_seq
        order_seq += int(rng.integers(7, 29))
        return f"ORD-{order_seq}"

    def _add_ticket(
        *,
        category: str,
        subject_tpl: str,
        body_tpl: str,
        signals: list[str],
        language: str,
        is_ambiguous: bool,
        secondary_category: str | None,
        channel: str,
        suffix: str = "",
    ) -> None:
        for _ in range(25):
            slots = {
                "product": str(rng.choice(PRODUCTS)),
                "order_id": _next_order_id(),
                "city": str(rng.choice(CITIES)),
                "date": str(rng.choice(DATES)),
            }
            subject = subject_tpl.format(**slots)
            body = (body_tpl.format(**slots) + suffix).strip()
            if body not in seen_bodies:
                seen_bodies.add(body)
                decision = evaluate_priority(set(signals), triage_config)
                tickets.append(
                    {
                        "id": f"EV-{len(tickets) + 1:03d}",
                        "subject": subject,
                        "body": body,
                        "channel": channel,
                        "language": language,
                        "true_category": category,
                        "true_signals": sorted(set(signals)),
                        "true_priority": decision.priority,
                        "is_ambiguous": is_ambiguous,
                        "secondary_category": secondary_category,
                    }
                )
                return
        raise RuntimeError(f"Could not produce unique body for category {category}")

    # 1. Include all 14 Hinglish tickets
    for idx, (cat, subj, body, sigs, ambig, sec_cat) in enumerate(HINGLISH_TICKETS):
        _add_ticket(
            category=cat,
            subject_tpl=subj,
            body_tpl=body,
            signals=sigs,
            language="hinglish",
            is_ambiguous=ambig,
            secondary_category=sec_cat,
            channel=CHANNELS[idx % len(CHANNELS)],
        )

    # 2. Include all 17 English ambiguous dual-category tickets (total ambiguous = 19)
    for idx, (cat, sec_cat, subj, body, sigs) in enumerate(AMBIGUOUS_TICKETS):
        _add_ticket(
            category=cat,
            subject_tpl=subj,
            body_tpl=body,
            signals=sigs,
            language="en",
            is_ambiguous=True,
            secondary_category=sec_cat,
            channel=CHANNELS[(idx + 1) % len(CHANNELS)],
        )

    # 3. Include all 14 very short (< 12 words) tickets
    for idx, (cat, subj, body, sigs, lang) in enumerate(SHORT_TICKETS):
        _add_ticket(
            category=cat,
            subject_tpl=subj,
            body_tpl=body,
            signals=sigs,
            language=lang,
            is_ambiguous=False,
            secondary_category=None,
            channel=CHANNELS[(idx + 2) % len(CHANNELS)],
        )

    # 4. Fill remaining 105 tickets (total = 150) evenly across all 7 categories (15 each)
    #    using every distinct template per category with varied tones/channels.
    tone_closings = [
        "",
        " Thanks in advance.",
        " Appreciate your quick help.",
        " Please reply on this thread.",
        " Looking forward to a prompt update.",
    ]
    categories_ordered = [cat.id for cat in triage_config.categories]
    remaining = 150 - len(tickets)
    per_cat = remaining // len(categories_ordered)
    extra = remaining % len(categories_ordered)

    for cat_idx, cat in enumerate(categories_ordered):
        templates = CATEGORY_TEMPLATES[cat]
        target_count = per_cat + (1 if cat_idx < extra else 0)
        for j in range(target_count):
            subj, body, sigs = templates[j % len(templates)]
            closing = tone_closings[(j // len(templates)) % len(tone_closings)]
            _add_ticket(
                category=cat,
                subject_tpl=subj,
                body_tpl=body,
                signals=sigs,
                language="en",
                is_ambiguous=False,
                secondary_category=None,
                channel=str(rng.choice(CHANNELS)),
                suffix=closing,
            )

    assert len(tickets) == 150
    return tickets


def compute_measured_effects(csv_path: Path, valid_categories: set[str]) -> dict[str, Any]:
    """Compute planted-effect measurements from CSV using pandas, excluding injected bad rows."""
    raw = pd.read_csv(csv_path, dtype={"ticket_id": str, "customer_id": str})
    total_rows = int(len(raw))

    created = pd.to_datetime(raw["created_at"], errors="coerce")
    assigned = pd.to_datetime(raw["assigned_at"], errors="coerce")
    first_resp = pd.to_datetime(raw["first_response_at"], errors="coerce")
    resolved = pd.to_datetime(raw["resolved_at"], errors="coerce")

    is_dup = raw["ticket_id"].duplicated(keep="first")
    is_missing_frt = (raw["status"] == "resolved") & first_resp.isna()
    is_frt_before_created = first_resp.notna() & (first_resp < created)
    is_unknown_cat = ~raw["category"].isin(valid_categories)
    is_missing_resolved = (raw["status"] == "resolved") & resolved.isna()
    is_over_300d = resolved.notna() & ((resolved - created) > pd.Timedelta(days=300))

    injected_measured = {
        "resolved_missing_first_response_at": int(is_missing_frt.sum()),
        "duplicate_ticket_ids": int(is_dup.sum()),
        "first_response_before_created": int(is_frt_before_created.sum()),
        "unknown_category_billing_misc": int((raw["category"] == "billing_misc").sum()),
        "resolved_missing_resolved_at": int(is_missing_resolved.sum()),
        "resolved_over_300_days": int(is_over_300d.sum()),
    }

    bad_mask = (
        is_dup
        | is_missing_frt
        | is_frt_before_created
        | is_unknown_cat
        | is_missing_resolved
        | is_over_300d
    )
    clean = raw.loc[~bad_mask].copy()
    clean["created_dt"] = created.loc[~bad_mask]
    clean["assigned_dt"] = assigned.loc[~bad_mask]
    clean["first_resp_dt"] = first_resp.loc[~bad_mask]
    clean["resolved_dt"] = resolved.loc[~bad_mask]

    clean["created_hour"] = clean["created_dt"].dt.hour
    clean["triage_lag_h"] = (clean["assigned_dt"] - clean["created_dt"]).dt.total_seconds() / 3600.0
    clean["agent_lag_h"] = (clean["first_resp_dt"] - clean["assigned_dt"]).dt.total_seconds() / 3600.0
    clean["frt_h"] = (clean["first_resp_dt"] - clean["created_dt"]).dt.total_seconds() / 3600.0

    staffed = clean[(clean["created_hour"] >= 9) & (clean["created_hour"] < 22)]
    median_triage_lag_staffed = float(staffed["triage_lag_h"].median())
    median_agent_lag_staffed = float(staffed["agent_lag_h"].median())
    median_frt_staffed = float(staffed["frt_h"].median())
    triage_share_staffed = float((staffed["triage_lag_h"] / staffed["frt_h"]).median())
    triage_share_all = float((clean["triage_lag_h"] / clean["frt_h"]).median())

    or_mask = clean["category"].isin(["order_tracking", "returns_refunds"])
    reassigned_order_returns = float((clean.loc[or_mask, "reassignment_count"] > 0).mean())
    reassigned_other = float((clean.loc[~or_mask, "reassignment_count"] > 0).mean())

    afternoon = clean[(clean["created_hour"] >= 14) & (clean["created_hour"] < 18)]
    evening = clean[(clean["created_hour"] >= 18) & (clean["created_hour"] < 22)]
    median_frt_afternoon = float(afternoon["frt_h"].median())
    median_frt_evening = float(evening["frt_h"].median())

    agent_counts = clean["assigned_agent"].value_counts()
    top3_agents = list(agent_counts.head(3).index)
    top3_share = float(agent_counts.head(3).sum() / len(clean))
    top3_frt = float(staffed.loc[staffed["assigned_agent"].isin(top3_agents), "frt_h"].median())
    other_frt = float(staffed.loc[~staffed["assigned_agent"].isin(top3_agents), "frt_h"].median())

    return {
        "total_rows": total_rows,
        "clean_rows": int(len(clean)),
        "distinct_customers": int(clean["customer_id"].nunique()),
        "median_triage_lag_staffed_hours": round(median_triage_lag_staffed, 3),
        "median_agent_response_lag_staffed_hours": round(median_agent_lag_staffed, 3),
        "median_first_response_staffed_hours": round(median_frt_staffed, 3),
        "triage_share_of_frt_staffed": round(triage_share_staffed, 4),
        "triage_share_of_frt_all": round(triage_share_all, 4),
        "reassignment_rate_order_and_returns": round(reassigned_order_returns, 4),
        "reassignment_rate_other_categories": round(reassigned_other, 4),
        "median_frt_afternoon_14_18_hours": round(median_frt_afternoon, 3),
        "median_frt_evening_18_22_hours": round(median_frt_evening, 3),
        "top_three_agents": top3_agents,
        "top_three_agent_volume_share": round(top3_share, 4),
        "top_three_vs_other_agent_frt_delta_hours": round(abs(top3_frt - other_frt), 3),
        "injected_quality_issues": injected_measured,
    }


def generate_all(output_dir: Path | None = None, seed: int = SEED) -> dict[str, Any]:
    """Generate sample_tickets.csv, eval_tickets.json, and answer_key.json deterministically."""
    target_dir = output_dir if output_dir is not None else (REPO_ROOT / "data")
    target_dir.mkdir(parents=True, exist_ok=True)

    triage_config = load_triage_config()
    rng_csv = np.random.default_rng(seed)
    rng_eval = np.random.default_rng(seed + 1000)

    ticket_rows = _generate_sample_tickets(rng_csv, triage_config)
    csv_path = target_dir / "sample_tickets.csv"
    with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ticket_rows)

    eval_tickets = _generate_eval_tickets(rng_eval, triage_config)
    eval_path = target_dir / "eval_tickets.json"
    eval_path.write_text(
        json.dumps(eval_tickets, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    valid_categories = {cat.id for cat in triage_config.categories}
    measured = compute_measured_effects(csv_path, valid_categories)

    answer_key = {
        "warning": (
            "Synthetic ground truth for tests and documentation only. "
            "Application code in backend/app must never import or read this file (R6)."
        ),
        "seed": seed,
        "period": {
            "start": _format_ts(PERIOD_START),
            "end": _format_ts(PERIOD_END),
            "timezone": "+05:30",
            "weeks": 8,
        },
        "planted_causes": [
            {
                "id": "slow_manual_triage",
                "strength": "dominant",
                "intended": "Median staffed created_at->assigned_at lag ~3-4h; ~55-65% share of total first-response time.",
            },
            {
                "id": "misrouting_order_and_returns",
                "strength": "strong_secondary",
                "intended": "order_tracking and returns_refunds reassigned ~35% vs ~8% for other categories (+1-3h per reassignment).",
            },
            {
                "id": "evening_coverage_gap",
                "strength": "moderate_secondary",
                "intended": "18:00-22:00 IST tickets (3 late-shift agents) wait >=1h longer than 14:00-18:00 IST (12 agents).",
            },
            {
                "id": "mild_workload_skew",
                "strength": "weak",
                "intended": "Top 3 agents carry ~40% of assigned volume with a small delay impact far below triage lag.",
            },
        ],
        "injected_quality_issues": dict(INJECTED_COUNTS),
        "measured_effects": measured,
        "eval_set_summary": {
            "total_tickets": len(eval_tickets),
            "ambiguous_count": sum(1 for t in eval_tickets if t["is_ambiguous"]),
            "hinglish_count": sum(1 for t in eval_tickets if t["language"] == "hinglish"),
            "short_under_12_words_count": sum(1 for t in eval_tickets if len(t["body"].split()) < 12),
            "urgency_or_delay_count": sum(
                1
                for t in eval_tickets
                if "explicit_urgency" in t["true_signals"]
                or "delivery_delayed_over_3_days" in t["true_signals"]
            ),
        },
    }

    answer_key_path = target_dir / "answer_key.json"
    answer_key_path.write_text(
        json.dumps(answer_key, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return answer_key


def main() -> None:
    summary = generate_all()
    m = summary["measured_effects"]
    issues = m["injected_quality_issues"]
    print("=== Groundwork Synthetic Data Summary (seed=42) ===")
    print(f"Row count: {m['total_rows']} total ({m['clean_rows']} clean, {m['distinct_customers']} distinct customers)")
    print(f"Median triage lag (staffed 09-22 IST): {m['median_triage_lag_staffed_hours']:.2f} h")
    print(f"Median agent response lag (staffed):   {m['median_agent_response_lag_staffed_hours']:.2f} h")
    print(f"Triage share of first-response time:   {m['triage_share_of_frt_staffed'] * 100:.1f}% (staffed), {m['triage_share_of_frt_all'] * 100:.1f}% (all)")
    print(
        f"Reassignment rate (order+returns vs other): "
        f"{m['reassignment_rate_order_and_returns'] * 100:.1f}% vs {m['reassignment_rate_other_categories'] * 100:.1f}%"
    )
    print(
        f"Median FRT by creation band (14-18 vs 18-22 IST): "
        f"{m['median_frt_afternoon_14_18_hours']:.2f} h vs {m['median_frt_evening_18_22_hours']:.2f} h"
    )
    print(
        f"Top-3 agent share of volume: {m['top_three_agent_volume_share'] * 100:.1f}% "
        f"({', '.join(m['top_three_agents'])}; FRT delta {m['top_three_vs_other_agent_frt_delta_hours']:.2f} h)"
    )
    print("Injected quality issues:")
    for key, value in issues.items():
        print(f"  - {key}: {value}")
    ev = summary["eval_set_summary"]
    print(
        f"Eval set: {ev['total_tickets']} tickets "
        f"(ambiguous={ev['ambiguous_count']}, hinglish={ev['hinglish_count']}, "
        f"short={ev['short_under_12_words_count']}, urgency_or_delay={ev['urgency_or_delay_count']})"
    )


if __name__ == "__main__":
    main()
