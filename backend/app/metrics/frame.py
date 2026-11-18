"""DataFrame builder and validation-scope filtering for stored Ticket rows."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metrics.config import MetricsConfig, load_metrics_config
from app.models import Dataset, Ticket

SCOPE_TO_AFFECTS: dict[str, set[str]] = {
    "all": {"all_metrics"},
    "response": {"all_metrics", "response_metrics"},
    "resolution": {"all_metrics", "resolution_metrics"},
    "triage": {"all_metrics", "triage_metrics"},
}

FRAME_COLUMNS = [
    "row_id",
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
    "is_valid",
    "validation_flags",
]


@dataclass(frozen=True)
class ScopeInfo:
    n_included: int
    n_excluded: int
    exclusions_by_flag_code: dict[str, int]


def _hour_to_band_map(config: MetricsConfig) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for band_name, window in config.creation_bands.items():
        for hour in window.covered_hours():
            mapping[hour] = band_name
    return mapping


def _to_utc_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def build_ticket_frame(
    records: Iterable[dict[str, Any]],
    config: MetricsConfig | None = None,
) -> pd.DataFrame:
    """Build a normalised tz-aware DataFrame with IST calendar and band columns."""
    metrics_config = config if config is not None else load_metrics_config()
    rows = list(records)
    if not rows:
        df = pd.DataFrame(columns=FRAME_COLUMNS)
    else:
        df = pd.DataFrame(rows)
        for col in FRAME_COLUMNS:
            if col not in df.columns:
                df[col] = None

    for ts_col in ("created_at", "assigned_at", "first_response_at", "resolved_at"):
        df[ts_col] = _to_utc_series(df[ts_col])

    tz = metrics_config.zone
    created_ist = df["created_at"].dt.tz_convert(tz)
    df["created_ist"] = created_ist
    df["created_date_ist"] = created_ist.dt.strftime("%Y-%m-%d")
    df["created_hour_ist"] = created_ist.dt.hour
    hour_map = _hour_to_band_map(metrics_config)
    df["creation_band"] = df["created_hour_ist"].map(
        lambda h: hour_map.get(int(h)) if pd.notna(h) else None
    )

    # Normalise validation_flags to always be a list of dicts.
    df["validation_flags"] = df["validation_flags"].apply(
        lambda val: list(val) if isinstance(val, list) else []
    )
    return df


def load_ticket_frame(
    db: Session,
    dataset_id: int,
    config: MetricsConfig | None = None,
) -> tuple[pd.DataFrame, datetime | None]:
    """Load Ticket rows for a dataset into a metrics DataFrame and return (df, as_of)."""
    metrics_config = config if config is not None else load_metrics_config()
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found.")

    tickets = db.scalars(
        select(Ticket)
        .where(Ticket.dataset_id == dataset_id)
        .order_by(Ticket.row_id.asc())
    ).all()

    records = [
        {
            "row_id": t.row_id,
            "ticket_id": t.ticket_id,
            "created_at": t.created_at,
            "assigned_at": t.assigned_at,
            "first_response_at": t.first_response_at,
            "resolved_at": t.resolved_at,
            "category": t.category,
            "priority": t.priority,
            "queue": t.queue,
            "assigned_agent": t.assigned_agent,
            "status": t.status,
            "channel": t.channel,
            "reassignment_count": t.reassignment_count,
            "customer_id": t.customer_id,
            "is_valid": t.is_valid,
            "validation_flags": t.validation_flags,
        }
        for t in tickets
    ]
    frame = build_ticket_frame(records, metrics_config)
    as_of = dataset.period_end
    if as_of is not None and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return frame, as_of


def scope(
    frame: pd.DataFrame,
    scope_name: str | Sequence[str],
) -> tuple[pd.DataFrame, ScopeInfo]:
    """Filter frame by validation scope(s) and report included, excluded, and flag counts."""
    if isinstance(scope_name, str):
        requested_scopes = [scope_name]
    else:
        requested_scopes = list(scope_name)

    target_affects: set[str] = set()
    for name in requested_scopes:
        if name not in SCOPE_TO_AFFECTS:
            raise ValueError(f"Unknown scope '{name}'.")
        target_affects.update(SCOPE_TO_AFFECTS[name])

    if frame.empty:
        return frame.copy(), ScopeInfo(n_included=0, n_excluded=0, exclusions_by_flag_code={})

    keep_mask: list[bool] = []
    exclusions_by_flag: dict[str, int] = {}

    for flags in frame["validation_flags"]:
        matching_codes: set[str] = set()
        if isinstance(flags, list):
            for flag in flags:
                if not isinstance(flag, dict):
                    continue
                flag_affects = set(flag.get("affects") or [])
                if flag_affects & target_affects:
                    code = str(flag.get("code", "unknown_flag"))
                    matching_codes.add(code)
        if matching_codes:
            keep_mask.append(False)
            for code in sorted(matching_codes):
                exclusions_by_flag[code] = exclusions_by_flag.get(code, 0) + 1
        else:
            keep_mask.append(True)

    mask_series = pd.Series(keep_mask, index=frame.index, dtype=bool)
    included_df = frame.loc[mask_series].copy()
    n_included = int(mask_series.sum())
    n_excluded = int(len(frame) - n_included)
    return included_df, ScopeInfo(
        n_included=n_included,
        n_excluded=n_excluded,
        exclusions_by_flag_code=dict(sorted(exclusions_by_flag.items())),
    )
