"""Pure deterministic operational metric computations (no DB access)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.metrics.config import ILLUSTRATIVE_SLA_NOTE, MetricsConfig
from app.metrics.frame import scope
from app.metrics.results import MetricResult
from app.metrics.stats import describe_hours, gini_coefficient

FACTOR_NON_CAUSAL_NOTE = (
    "Observed association only. Groups differ in other ways, differences overlap "
    "and are not additive, and this is not an estimate of effect."
)

RIGHT_CENSORING_RESPONSE_NOTE = (
    "Unanswered tickets are excluded from first-response time statistics and "
    "reported separately as unanswered_count (right-censoring)."
)

RIGHT_CENSORING_RESOLUTION_NOTE = (
    "Unresolved tickets (open or pending) are excluded from resolution time "
    "statistics and reported separately as unresolved_count (right-censoring)."
)

BACKLOG_SNAPSHOT_NOTE = (
    "Ticket status is an extraction-time snapshot; backlog age is measured in "
    "days as of the dataset period_end."
)

KNOWN_CHANNELS = {"email", "chat", "web_form", "whatsapp"}


def _hours_between(later: pd.Series, earlier: pd.Series) -> pd.Series:
    return (later - earlier).dt.total_seconds() / 3600.0


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_valid_reassignment_counts(
    df: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Return (valid_mask, integer_series) for reassignment_count values."""
    valid_flags: list[bool] = []
    parsed_vals: list[int | None] = []

    for val in df["reassignment_count"]:
        if val is None or isinstance(val, bool) or pd.isna(val):
            valid_flags.append(False)
            parsed_vals.append(None)
            continue
        if isinstance(val, int):
            if val >= 0:
                valid_flags.append(True)
                parsed_vals.append(val)
            else:
                valid_flags.append(False)
                parsed_vals.append(None)
            continue
        if isinstance(val, float):
            if val.is_integer() and val >= 0:
                valid_flags.append(True)
                parsed_vals.append(int(val))
            else:
                valid_flags.append(False)
                parsed_vals.append(None)
            continue
        text = str(val).strip()
        if not text:
            valid_flags.append(False)
            parsed_vals.append(None)
            continue
        try:
            num = int(text)
            if num >= 0 and str(num) == text.lstrip("+"):
                valid_flags.append(True)
                parsed_vals.append(num)
            else:
                valid_flags.append(False)
                parsed_vals.append(None)
        except ValueError:
            valid_flags.append(False)
            parsed_vals.append(None)

    return (
        pd.Series(valid_flags, index=df.index, dtype=bool),
        pd.Series(parsed_vals, index=df.index, dtype="object"),
    )


def first_response_time(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "response")
    has_frt = scoped["first_response_at"].notna() & scoped["created_at"].notna()
    unanswered_count = int((~has_frt).sum())
    hours = _hours_between(
        scoped.loc[has_frt, "first_response_at"],
        scoped.loc[has_frt, "created_at"],
    )
    summary = describe_hours(hours)
    summary["unanswered_count"] = unanswered_count

    return MetricResult(
        metric_id="first_response_time",
        title="First-response time",
        definition=(
            "Elapsed hours from ticket creation (created_at) to first agent response "
            "(first_response_at) among response-valid tickets with a recorded response."
        ),
        unit="hours",
        scope="response",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=summary,
        notes=[
            RIGHT_CENSORING_RESPONSE_NOTE,
            "Includes overnight waiting outside staffed hours (09:00-22:00 IST).",
        ],
        as_of=_ensure_utc(as_of),
    )


def agent_response_time(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, ("response", "triage"))
    both_mask = scoped["first_response_at"].notna() & scoped["assigned_at"].notna()
    hours = _hours_between(
        scoped.loc[both_mask, "first_response_at"],
        scoped.loc[both_mask, "assigned_at"],
    )
    summary = describe_hours(hours)
    summary["missing_timestamp_count"] = int((~both_mask).sum())

    return MetricResult(
        metric_id="agent_response_time",
        title="Agent response time",
        definition=(
            "Elapsed hours from assignment (assigned_at) to first response "
            "(first_response_at) among tickets valid for both response and triage scopes."
        ),
        unit="hours",
        scope="response+triage",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=summary,
        notes=[
            "Computed only over tickets with both assigned_at and first_response_at present."
        ],
        as_of=_ensure_utc(as_of),
    )


def triage_time(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "triage")
    has_assign = scoped["assigned_at"].notna() & scoped["created_at"].notna()
    hours = _hours_between(
        scoped.loc[has_assign, "assigned_at"],
        scoped.loc[has_assign, "created_at"],
    )
    summary = describe_hours(hours)
    summary["unassigned_count"] = int((~has_assign).sum())

    return MetricResult(
        metric_id="triage_time",
        title="Time to assignment (triage lag)",
        definition=(
            "Elapsed hours from ticket creation (created_at) to assignment "
            "(assigned_at) among triage-valid tickets with an assignment timestamp."
        ),
        unit="hours",
        scope="triage",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=summary,
        notes=["Includes overnight queue waiting for tickets created outside staffed hours."],
        as_of=_ensure_utc(as_of),
    )


def triage_share_of_first_response(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, ("response", "triage"))
    mask = (
        scoped["created_at"].notna()
        & scoped["assigned_at"].notna()
        & scoped["first_response_at"].notna()
    )
    subset = scoped.loc[mask]
    n = int(len(subset))
    if n == 0:
        data: dict[str, Any] = {
            "n": 0,
            "triage_hours_sum": 0.0,
            "first_response_hours_sum": 0.0,
            "share": None,
        }
    else:
        triage_sum = float(
            _hours_between(subset["assigned_at"], subset["created_at"]).sum()
        )
        frt_sum = float(
            _hours_between(subset["first_response_at"], subset["created_at"]).sum()
        )
        share = float(triage_sum / frt_sum) if frt_sum > 0 else None
        data = {
            "n": n,
            "triage_hours_sum": triage_sum,
            "first_response_hours_sum": frt_sum,
            "share": share,
        }

    return MetricResult(
        metric_id="triage_share_of_first_response",
        title="Triage share of first-response time",
        definition=(
            "Aggregate ratio sum(assigned_at - created_at) / sum(first_response_at - created_at) "
            "over tickets valid for both response and triage scopes with all three timestamps."
        ),
        unit="ratio",
        scope="response+triage",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=data,
        notes=[
            "Aggregate sum ratio across all creation hours (including overnight waiting)."
        ],
        as_of=_ensure_utc(as_of),
    )


def resolution_time(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "resolution")
    is_resolved = (
        (scoped["status"] == "resolved")
        & scoped["resolved_at"].notna()
        & scoped["created_at"].notna()
    )
    unresolved_count = int((~is_resolved).sum())
    hours = _hours_between(
        scoped.loc[is_resolved, "resolved_at"],
        scoped.loc[is_resolved, "created_at"],
    )
    summary = describe_hours(hours)
    summary["unresolved_count"] = unresolved_count

    return MetricResult(
        metric_id="resolution_time",
        title="Resolution time",
        definition=(
            "Elapsed hours from ticket creation (created_at) to resolution "
            "(resolved_at) among resolution-valid resolved tickets."
        ),
        unit="hours",
        scope="resolution",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=summary,
        notes=[RIGHT_CENSORING_RESOLUTION_NOTE],
        as_of=_ensure_utc(as_of),
    )


def volume_by_day(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    total = int(len(scoped))
    rows: list[dict[str, Any]] = []
    if total > 0:
        counts = scoped["created_date_ist"].value_counts().sort_index()
        for date_str, count in counts.items():
            cnt = int(count)
            rows.append({"date": str(date_str), "count": cnt, "share": cnt / total})

    return MetricResult(
        metric_id="volume_by_day",
        title="Daily ticket volume",
        definition=f"Ticket counts and shares grouped by creation date in {config.timezone}.",
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params={"timezone": config.timezone, **(params or {})},
        data=rows,
        notes=[f"Dates use {config.timezone} calendar boundaries."],
        as_of=_ensure_utc(as_of),
    )


def volume_by_hour(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    total = int(len(scoped))
    counts = scoped["created_hour_ist"].value_counts().to_dict() if total > 0 else {}
    rows = [
        {
            "hour": h,
            "count": int(counts.get(h, 0)),
            "share": (int(counts.get(h, 0)) / total) if total > 0 else 0.0,
        }
        for h in range(24)
    ]

    return MetricResult(
        metric_id="volume_by_hour",
        title="Ticket volume by hour of day",
        definition=f"Ticket counts and shares by creation hour (0-23) in {config.timezone}.",
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params={"timezone": config.timezone, **(params or {})},
        data=rows,
        notes=[
            f"Staffed hours in configuration: {config.staffed_hours.start:02d}:00-"
            f"{config.staffed_hours.end:02d}:00 {config.timezone}."
        ],
        as_of=_ensure_utc(as_of),
    )


def volume_by_band(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    total = int(len(scoped))
    counts = scoped["creation_band"].value_counts().to_dict() if total > 0 else {}
    rows = []
    for band_name, window in config.creation_bands.items():
        cnt = int(counts.get(band_name, 0))
        rows.append(
            {
                "band": band_name,
                "hours": f"{window.start:02d}:00-{window.end:02d}:00",
                "count": cnt,
                "share": (cnt / total) if total > 0 else 0.0,
            }
        )

    return MetricResult(
        metric_id="volume_by_band",
        title="Ticket volume by creation band",
        definition=f"Ticket counts and shares by configured {config.timezone} creation-hour band.",
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params={"timezone": config.timezone, **(params or {})},
        data=rows,
        notes=["Bands use [start, end) hour intervals in IST; overnight wraps midnight."],
        as_of=_ensure_utc(as_of),
    )


def volume_by_category(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    total = int(len(scoped))
    rows: list[dict[str, Any]] = []
    if total > 0:
        counts = scoped["category"].fillna("unknown").value_counts()
        sorted_items = sorted(counts.items(), key=lambda pair: (-int(pair[1]), str(pair[0])))
        for category, count in sorted_items:
            cnt = int(count)
            rows.append({"category": str(category), "count": cnt, "share": cnt / total})

    return MetricResult(
        metric_id="volume_by_category",
        title="Ticket volume by category",
        definition="Ticket counts and shares grouped by validated category.",
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=rows,
        notes=["Rows with unknown categories are excluded under the all scope."],
        as_of=_ensure_utc(as_of),
    )


def volume_by_channel(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    total = int(len(scoped))
    rows: list[dict[str, Any]] = []
    if total > 0:
        normalised = scoped["channel"].apply(
            lambda ch: str(ch) if isinstance(ch, str) and ch in KNOWN_CHANNELS else "unknown"
        )
        counts = normalised.value_counts()
        sorted_items = sorted(counts.items(), key=lambda pair: (-int(pair[1]), str(pair[0])))
        for channel, count in sorted_items:
            cnt = int(count)
            rows.append({"channel": str(channel), "count": cnt, "share": cnt / total})

    return MetricResult(
        metric_id="volume_by_channel",
        title="Ticket volume by channel",
        definition="Ticket counts and shares grouped by customer contact channel.",
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data=rows,
        notes=["Channels outside the closed vocabulary are bucketed as unknown."],
        as_of=_ensure_utc(as_of),
    )


def first_response_by_band(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "response")
    has_frt = scoped["first_response_at"].notna() & scoped["created_at"].notna()
    responded = scoped.loc[has_frt].copy()
    if not responded.empty:
        responded["frt_hours"] = _hours_between(
            responded["first_response_at"], responded["created_at"]
        )

    rows: list[dict[str, Any]] = []
    for band_name, window in config.creation_bands.items():
        if responded.empty:
            stats = describe_hours([])
        else:
            band_series = responded.loc[responded["creation_band"] == band_name, "frt_hours"]
            stats = describe_hours(band_series)
        rows.append(
            {
                "band": band_name,
                "hours": f"{window.start:02d}:00-{window.end:02d}:00",
                **stats,
            }
        )

    return MetricResult(
        metric_id="first_response_by_band",
        title="First-response time by creation band",
        definition=(
            f"First-response time distribution (n, median, p90, mean) by {config.timezone} "
            "creation-hour band among response-valid tickets with a recorded response."
        ),
        unit="hours",
        scope="response",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params={"timezone": config.timezone, **(params or {})},
        data=rows,
        notes=[
            RIGHT_CENSORING_RESPONSE_NOTE,
            "Overnight band includes unstaffed waiting time until next shift start.",
        ],
        as_of=_ensure_utc(as_of),
    )


def category_delay_table(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped_all, info_all = scope(frame, "all")
    scoped_triage, _ = scope(frame, "triage")
    scoped_resp, _ = scope(frame, "response")
    scoped_res, _ = scope(frame, "resolution")

    rows: list[dict[str, Any]] = []
    if not scoped_all.empty:
        valid_re_mask, parsed_re = _parse_valid_reassignment_counts(scoped_all)
        scoped_all_re = scoped_all.loc[valid_re_mask].copy()
        scoped_all_re["re_int"] = parsed_re.loc[valid_re_mask].astype(int)

        categories = sorted(
            scoped_all["category"].dropna().unique(),
            key=lambda c: (-int((scoped_all["category"] == c).sum()), str(c)),
        )
        for cat in categories:
            n_cat = int((scoped_all["category"] == cat).sum())

            t_sub = scoped_triage[
                (scoped_triage["category"] == cat)
                & scoped_triage["assigned_at"].notna()
                & scoped_triage["created_at"].notna()
            ]
            t_stats = describe_hours(_hours_between(t_sub["assigned_at"], t_sub["created_at"]))

            f_sub = scoped_resp[
                (scoped_resp["category"] == cat)
                & scoped_resp["first_response_at"].notna()
                & scoped_resp["created_at"].notna()
            ]
            f_stats = describe_hours(
                _hours_between(f_sub["first_response_at"], f_sub["created_at"])
            )

            r_sub = scoped_res[
                (scoped_res["category"] == cat)
                & (scoped_res["status"] == "resolved")
                & scoped_res["resolved_at"].notna()
                & scoped_res["created_at"].notna()
            ]
            r_stats = describe_hours(_hours_between(r_sub["resolved_at"], r_sub["created_at"]))

            re_sub = scoped_all_re[scoped_all_re["category"] == cat]
            re_rate = (
                float((re_sub["re_int"] >= 1).mean()) if len(re_sub) > 0 else None
            )

            rows.append(
                {
                    "category": str(cat),
                    "n": n_cat,
                    "median_triage_hours": t_stats["median"],
                    "median_first_response_hours": f_stats["median"],
                    "median_resolution_hours": r_stats["median"],
                    "reassignment_rate": re_rate,
                }
            )

    return MetricResult(
        metric_id="category_delay_table",
        title="Category delay and reassignment breakdown",
        definition=(
            "Per-category ticket count, median triage lag, median first-response time, "
            "median resolution time, and reassignment rate using each metric's validation scope."
        ),
        unit="mixed",
        scope="all",
        n_included=info_all.n_included,
        n_excluded=info_all.n_excluded,
        exclusions=info_all.exclusions_by_flag_code,
        params=dict(params or {}),
        data=rows,
        notes=[
            "Each column applies its own validation scope (triage, response, resolution, all)."
        ],
        as_of=_ensure_utc(as_of),
    )


def backlog_ageing(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    as_of_utc = _ensure_utc(as_of)

    open_mask = scoped["status"].isin(["open", "pending"]) & scoped["created_at"].notna()
    backlog = scoped.loc[open_mask].copy()
    total_backlog = int(len(backlog))

    ordered_buckets = sorted(
        config.ageing_buckets_days.items(), key=lambda pair: pair[1].min
    )
    bucket_counts = {name: 0 for name, _ in ordered_buckets}
    oldest_age_days: float | None = None

    if total_backlog > 0 and as_of_utc is not None:
        ages_days = (
            (pd.Timestamp(as_of_utc) - backlog["created_at"]).dt.total_seconds() / 86400.0
        ).clip(lower=0.0)
        backlog["age_days"] = ages_days
        oldest_age_days = float(ages_days.max())

        for age in ages_days:
            for bucket_name, bucket in ordered_buckets:
                if bucket.max is None:
                    if age >= bucket.min:
                        bucket_counts[bucket_name] += 1
                        break
                elif bucket.min <= age < bucket.max:
                    bucket_counts[bucket_name] += 1
                    break

    buckets_out = [
        {
            "bucket": name,
            "min_days": bucket.min,
            "max_days": bucket.max,
            "count": bucket_counts[name],
            "share": (bucket_counts[name] / total_backlog) if total_backlog > 0 else 0.0,
        }
        for name, bucket in ordered_buckets
    ]

    by_category: list[dict[str, Any]] = []
    if total_backlog > 0:
        cat_counts = backlog["category"].fillna("unknown").value_counts()
        for cat, cnt in sorted(cat_counts.items(), key=lambda p: (-int(p[1]), str(p[0]))):
            by_category.append(
                {"category": str(cat), "count": int(cnt), "share": int(cnt) / total_backlog}
            )

    return MetricResult(
        metric_id="backlog_ageing",
        title="Open backlog ageing",
        definition=(
            "Counts and shares of open and pending tickets grouped by age in days "
            "as of dataset period_end, plus breakdown by category and oldest ticket age."
        ),
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params=dict(params or {}),
        data={
            "total_open_backlog": total_backlog,
            "oldest_age_days": oldest_age_days,
            "buckets": buckets_out,
            "by_category": by_category,
        },
        notes=[BACKLOG_SNAPSHOT_NOTE],
        as_of=as_of_utc,
    )


def agent_workload(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    top_n = int((params or {}).get("top_n", config.findings_thresholds.workload.top_n))

    has_agent = scoped["assigned_agent"].notna() & (
        scoped["assigned_agent"].astype(str).str.strip() != ""
    )
    unassigned_count = int((~has_agent).sum())
    assigned = scoped.loc[has_agent]
    assigned_total = int(len(assigned))

    agents_out: list[dict[str, Any]] = []
    top_n_agents: list[str] = []
    top_n_share: float | None = None
    gini: float | None = None

    if assigned_total > 0:
        counts = assigned["assigned_agent"].astype(str).value_counts()
        sorted_items = sorted(counts.items(), key=lambda pair: (-int(pair[1]), str(pair[0])))
        for agent_name, count in sorted_items:
            cnt = int(count)
            agents_out.append(
                {"agent": str(agent_name), "count": cnt, "share": cnt / assigned_total}
            )
        top_slice = agents_out[:top_n]
        top_n_agents = [item["agent"] for item in top_slice]
        top_n_share = float(sum(item["count"] for item in top_slice) / assigned_total)
        gini = gini_coefficient([item["count"] for item in agents_out])

    return MetricResult(
        metric_id="agent_workload",
        title="Agent workload distribution",
        definition=(
            "Assigned ticket counts and shares per agent, top-N agent volume share, "
            "and Gini coefficient across assigned agents; unassigned tickets reported separately."
        ),
        unit="tickets",
        scope="all",
        n_included=info.n_included,
        n_excluded=info.n_excluded,
        exclusions=info.exclusions_by_flag_code,
        params={"top_n": top_n},
        data={
            "assigned_total": assigned_total,
            "unassigned_count": unassigned_count,
            "top_n": top_n,
            "top_n_agents": top_n_agents,
            "top_n_share": top_n_share,
            "gini": gini,
            "agents": agents_out,
        },
        notes=[
            "Workload share reflects final assigned_agent only and does not capture shift lengths or complexity."
        ],
        as_of=_ensure_utc(as_of),
    )


def reassignment_rate(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "all")
    exclusions = dict(info.exclusions_by_flag_code)

    if scoped.empty:
        usable = scoped
        unusable_count = 0
    else:
        valid_mask, parsed_vals = _parse_valid_reassignment_counts(scoped)
        unusable_count = int((~valid_mask).sum())
        usable = scoped.loc[valid_mask].copy()
        usable["re_int"] = parsed_vals.loc[valid_mask].astype(int)

    if unusable_count > 0:
        exclusions["reassignment_count_unusable"] = unusable_count

    n_included = int(len(usable))
    n_excluded = info.n_excluded + unusable_count

    if n_included == 0:
        overall = {"n": 0, "reassigned_count": 0, "rate": None, "mean_reassignments": None}
        by_category: list[dict[str, Any]] = []
        by_queue: list[dict[str, Any]] = []
    else:
        reassigned_total = int((usable["re_int"] >= 1).sum())
        overall = {
            "n": n_included,
            "reassigned_count": reassigned_total,
            "rate": float(reassigned_total / n_included),
            "mean_reassignments": float(usable["re_int"].mean()),
        }

        by_category = []
        for cat, group in usable.groupby(usable["category"].fillna("unknown")):
            g_n = int(len(group))
            g_re = int((group["re_int"] >= 1).sum())
            by_category.append(
                {
                    "category": str(cat),
                    "n": g_n,
                    "reassigned_count": g_re,
                    "rate": float(g_re / g_n),
                    "mean_reassignments": float(group["re_int"].mean()),
                }
            )
        by_category.sort(key=lambda r: (-r["rate"], -r["n"], r["category"]))

        by_queue = []
        for queue_name, group in usable.groupby(usable["queue"].fillna("unknown")):
            g_n = int(len(group))
            g_re = int((group["re_int"] >= 1).sum())
            by_queue.append(
                {
                    "queue": str(queue_name),
                    "n": g_n,
                    "reassigned_count": g_re,
                    "rate": float(g_re / g_n),
                    "mean_reassignments": float(group["re_int"].mean()),
                }
            )
        by_queue.sort(key=lambda r: (-r["rate"], -r["n"], r["queue"]))

    return MetricResult(
        metric_id="reassignment_rate",
        title="Ticket reassignment rate",
        definition=(
            "Share of tickets with reassignment_count >= 1 and mean reassignment count "
            "overall, by category, and by queue."
        ),
        unit="ratio",
        scope="all",
        n_included=n_included,
        n_excluded=n_excluded,
        exclusions=exclusions,
        params=dict(params or {}),
        data={
            "overall": overall,
            "by_category": by_category,
            "by_queue": by_queue,
        },
        notes=[
            "Rows with blank, negative, or non-integer reassignment_count are excluded as reassignment_count_unusable."
        ],
        as_of=_ensure_utc(as_of),
    )


def reassigned_vs_not(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    scoped, info = scope(frame, "response")
    exclusions = dict(info.exclusions_by_flag_code)

    if scoped.empty:
        usable = scoped
        unusable_count = 0
    else:
        valid_mask, parsed_vals = _parse_valid_reassignment_counts(scoped)
        unusable_count = int((~valid_mask).sum())
        usable = scoped.loc[valid_mask].copy()
        usable["re_int"] = parsed_vals.loc[valid_mask].astype(int)

    if unusable_count > 0:
        exclusions["reassignment_count_unusable"] = unusable_count

    has_frt = usable["first_response_at"].notna() & usable["created_at"].notna()
    responded = usable.loc[has_frt].copy()
    if not responded.empty:
        responded["frt_hours"] = _hours_between(
            responded["first_response_at"], responded["created_at"]
        )
        re_stats = describe_hours(responded.loc[responded["re_int"] >= 1, "frt_hours"])
        no_stats = describe_hours(responded.loc[responded["re_int"] == 0, "frt_hours"])
    else:
        re_stats = describe_hours([])
        no_stats = describe_hours([])

    diff_hours = (
        float(re_stats["median"] - no_stats["median"])
        if re_stats["median"] is not None and no_stats["median"] is not None
        else None
    )

    return MetricResult(
        metric_id="reassigned_vs_not",
        title="First-response time: reassigned vs not reassigned",
        definition=(
            "Comparison of first-response time distributions between tickets with "
            "reassignment_count >= 1 and tickets with reassignment_count == 0."
        ),
        unit="hours",
        scope="response",
        n_included=int(len(usable)),
        n_excluded=info.n_excluded + unusable_count,
        exclusions=exclusions,
        params=dict(params or {}),
        data={
            "reassigned": re_stats,
            "not_reassigned": no_stats,
            "median_difference_hours": diff_hours,
        },
        notes=[RIGHT_CENSORING_RESPONSE_NOTE, FACTOR_NON_CAUSAL_NOTE],
        as_of=_ensure_utc(as_of),
    )


def sla_attainment(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    as_of_utc = _ensure_utc(as_of)
    frt_threshold = float(
        (params or {}).get("first_response_hours", config.sla.first_response_hours)
    )
    res_threshold = float(
        (params or {}).get("resolution_hours", config.sla.resolution_hours)
    )

    resp_scoped, resp_info = scope(frame, "response")
    has_frt = resp_scoped["first_response_at"].notna() & resp_scoped["created_at"].notna()
    responded = resp_scoped.loc[has_frt]
    responded_n = int(len(responded))
    if responded_n > 0:
        frt_hours = _hours_between(responded["first_response_at"], responded["created_at"])
        frt_met = int((frt_hours <= frt_threshold).sum())
        frt_rate: float | None = float(frt_met / responded_n)
    else:
        frt_met = 0
        frt_rate = None

    unanswered = resp_scoped.loc[~has_frt & resp_scoped["created_at"].notna()]
    if len(unanswered) > 0 and as_of_utc is not None:
        unanswered_age_h = (
            pd.Timestamp(as_of_utc) - unanswered["created_at"]
        ).dt.total_seconds() / 3600.0
        unanswered_past_threshold = int((unanswered_age_h > frt_threshold).sum())
    else:
        unanswered_past_threshold = 0

    res_scoped, res_info = scope(frame, "resolution")
    is_resolved = (
        (res_scoped["status"] == "resolved")
        & res_scoped["resolved_at"].notna()
        & res_scoped["created_at"].notna()
    )
    resolved = res_scoped.loc[is_resolved]
    resolved_n = int(len(resolved))
    if resolved_n > 0:
        res_hours = _hours_between(resolved["resolved_at"], resolved["created_at"])
        res_met = int((res_hours <= res_threshold).sum())
        res_rate: float | None = float(res_met / resolved_n)
    else:
        res_met = 0
        res_rate = None

    unresolved = res_scoped.loc[~is_resolved & res_scoped["created_at"].notna()]
    if len(unresolved) > 0 and as_of_utc is not None:
        unresolved_age_h = (
            pd.Timestamp(as_of_utc) - unresolved["created_at"]
        ).dt.total_seconds() / 3600.0
        unresolved_past_threshold = int((unresolved_age_h > res_threshold).sum())
    else:
        unresolved_past_threshold = 0

    combined_exclusions = dict(resp_info.exclusions_by_flag_code)
    for code, count in res_info.exclusions_by_flag_code.items():
        combined_exclusions[code] = max(combined_exclusions.get(code, 0), count)

    return MetricResult(
        metric_id="sla_attainment",
        title="SLA attainment (illustrative thresholds)",
        definition=(
            f"Share of responded tickets meeting the {frt_threshold:g}h first-response "
            f"threshold and resolved tickets meeting the {res_threshold:g}h resolution "
            "threshold, with unanswered/unresolved tickets already past threshold reported separately."
        ),
        unit="ratio",
        scope="response",
        n_included=resp_info.n_included,
        n_excluded=resp_info.n_excluded,
        exclusions=resp_info.exclusions_by_flag_code,
        params={
            "first_response_hours": frt_threshold,
            "resolution_hours": res_threshold,
        },
        data={
            "first_response": {
                "threshold_hours": frt_threshold,
                "responded_n": responded_n,
                "met_count": frt_met,
                "attainment_rate": frt_rate,
                "unanswered_past_threshold_count": unanswered_past_threshold,
            },
            "resolution": {
                "threshold_hours": res_threshold,
                "resolved_n": resolved_n,
                "met_count": res_met,
                "attainment_rate": res_rate,
                "unresolved_past_threshold_count": unresolved_past_threshold,
            },
        },
        notes=[
            ILLUSTRATIVE_SLA_NOTE,
            RIGHT_CENSORING_RESPONSE_NOTE,
            RIGHT_CENSORING_RESOLUTION_NOTE,
        ],
        as_of=as_of_utc,
    )


def factor_comparison(
    frame: pd.DataFrame,
    config: MetricsConfig,
    as_of: datetime | None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    re_result = reassigned_vs_not(frame, config, as_of)
    band_result = first_response_by_band(frame, config, as_of)
    workload_result = agent_workload(frame, config, as_of)
    triage_result = triage_time(frame, config, as_of)
    frt_result = first_response_time(frame, config, as_of)

    band_by_name = {row["band"]: row for row in band_result.data}
    evening_row = band_by_name.get("evening", {"n": 0, "median": None})
    afternoon_row = band_by_name.get("afternoon", {"n": 0, "median": None})
    evening_diff = (
        float(evening_row["median"] - afternoon_row["median"])
        if evening_row["median"] is not None and afternoon_row["median"] is not None
        else None
    )

    top_n = config.findings_thresholds.workload.top_n
    top_agents = set(workload_result.data["top_n_agents"])
    resp_scoped, resp_info = scope(frame, "response")
    has_frt = resp_scoped["first_response_at"].notna() & resp_scoped["created_at"].notna()
    responded = resp_scoped.loc[has_frt].copy()
    if not responded.empty:
        responded["frt_hours"] = _hours_between(
            responded["first_response_at"], responded["created_at"]
        )
        has_agent = responded["assigned_agent"].notna() & (
            responded["assigned_agent"].astype(str).str.strip() != ""
        )
        assigned_resp = responded.loc[has_agent]
        top_stats = describe_hours(
            assigned_resp.loc[assigned_resp["assigned_agent"].isin(top_agents), "frt_hours"]
        )
        other_stats = describe_hours(
            assigned_resp.loc[~assigned_resp["assigned_agent"].isin(top_agents), "frt_hours"]
        )
    else:
        top_stats = describe_hours([])
        other_stats = describe_hours([])

    workload_diff = (
        float(top_stats["median"] - other_stats["median"])
        if top_stats["median"] is not None and other_stats["median"] is not None
        else None
    )

    rows = [
        {
            "factor_id": "reassigned_vs_not",
            "factor": "Reassigned vs not reassigned",
            "group_a_label": "Reassigned (>= 1)",
            "group_a_median_hours": re_result.data["reassigned"]["median"],
            "group_a_n": re_result.data["reassigned"]["n"],
            "group_b_label": "Not reassigned (0)",
            "group_b_median_hours": re_result.data["not_reassigned"]["median"],
            "group_b_n": re_result.data["not_reassigned"]["n"],
            "difference_hours": re_result.data["median_difference_hours"],
            "note": FACTOR_NON_CAUSAL_NOTE,
        },
        {
            "factor_id": "evening_vs_afternoon",
            "factor": "Evening vs afternoon creation band",
            "group_a_label": "Evening (18:00-22:00 IST)",
            "group_a_median_hours": evening_row["median"],
            "group_a_n": evening_row["n"],
            "group_b_label": "Afternoon (14:00-18:00 IST)",
            "group_b_median_hours": afternoon_row["median"],
            "group_b_n": afternoon_row["n"],
            "difference_hours": evening_diff,
            "note": FACTOR_NON_CAUSAL_NOTE,
        },
        {
            "factor_id": "top_n_agents_vs_others",
            "factor": f"Top-{top_n} agents vs other agents",
            "group_a_label": f"Top-{top_n} agents' tickets",
            "group_a_median_hours": top_stats["median"],
            "group_a_n": top_stats["n"],
            "group_b_label": "Other agents' tickets",
            "group_b_median_hours": other_stats["median"],
            "group_b_n": other_stats["n"],
            "difference_hours": workload_diff,
            "note": FACTOR_NON_CAUSAL_NOTE,
        },
        {
            "factor_id": "time_to_assignment",
            "factor": "Median time to assignment (triage lag)",
            "group_a_label": "Time to assignment",
            "group_a_median_hours": triage_result.data["median"],
            "group_a_n": triage_result.data["n"],
            "group_b_label": "Total first-response time",
            "group_b_median_hours": frt_result.data["median"],
            "group_b_n": frt_result.data["n"],
            "difference_hours": triage_result.data["median"],
            "note": FACTOR_NON_CAUSAL_NOTE,
        },
    ]

    return MetricResult(
        metric_id="factor_comparison",
        title="Factor comparison (observed associations)",
        definition=(
            "Side-by-side median first-response comparisons across reassigned status, "
            "evening vs afternoon creation bands, top-N vs other agents, plus median time to assignment."
        ),
        unit="hours",
        scope="response",
        n_included=resp_info.n_included,
        n_excluded=resp_info.n_excluded,
        exclusions=resp_info.exclusions_by_flag_code,
        params={"top_n": top_n},
        data=rows,
        notes=[FACTOR_NON_CAUSAL_NOTE],
        as_of=_ensure_utc(as_of),
    )
