"""Deterministic row-level and dataset-level validation for uploaded ticket CSVs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.ingest.parse import ParsedCSV
from app.triage.config import TriageConfig

IMPLAUSIBLE_DURATION_DAYS = 180
DEFAULT_TIMEZONE = ZoneInfo("Asia/Kolkata")

VALID_STATUSES: frozenset[str] = frozenset({"open", "pending", "resolved"})
VALID_CHANNELS: frozenset[str] = frozenset({"email", "chat", "web_form", "whatsapp"})
VALID_PRIORITIES: frozenset[str] = frozenset({"low", "medium", "high"})

CHECK_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "code": "missing_or_invalid_created_at",
        "severity": "warning",
        "affects": ["all_metrics"],
        "message": "Ticket has a missing or unparseable creation timestamp.",
        "recommended_action": "Verify the created_at column uses ISO 8601 format and re-export affected rows.",
    },
    {
        "code": "duplicate_ticket_id",
        "severity": "warning",
        "affects": ["all_metrics"],
        "message": "Duplicate ticket_id detected; second and later occurrences are excluded from all metrics.",
        "recommended_action": "Deduplicate ticket exports by ticket_id before running downstream KPI baselines.",
    },
    {
        "code": "unknown_category",
        "severity": "warning",
        "affects": ["all_metrics"],
        "message": "Category is not in the configured queue taxonomy (config/queues.yaml).",
        "recommended_action": "Map unrecognised categories to an approved taxonomy category or update config/queues.yaml.",
    },
    {
        "code": "first_response_before_created",
        "severity": "warning",
        "affects": ["response_metrics"],
        "message": "First-response timestamp is earlier than the ticket creation timestamp.",
        "recommended_action": "Check helpdesk timezone exports or clock drift; rows are excluded from response-time metrics.",
    },
    {
        "code": "missing_first_response_on_resolved",
        "severity": "warning",
        "affects": ["response_metrics"],
        "message": "Ticket is marked resolved but has no valid first_response_at timestamp.",
        "recommended_action": "Confirm whether tickets were auto-closed without a reply; excluded from response-time metrics.",
    },
    {
        "code": "missing_resolved_at_on_resolved",
        "severity": "warning",
        "affects": ["resolution_metrics"],
        "message": "Ticket is marked resolved but has no valid resolved_at timestamp.",
        "recommended_action": "Backfill resolution timestamps in the helpdesk export; excluded from resolution-time metrics.",
    },
    {
        "code": "resolved_before_created",
        "severity": "warning",
        "affects": ["resolution_metrics"],
        "message": "Resolution timestamp is earlier than the ticket creation timestamp.",
        "recommended_action": "Inspect timestamp ordering in the source system; excluded from resolution-time metrics.",
    },
    {
        "code": "implausible_duration",
        "severity": "warning",
        "affects": ["resolution_metrics"],
        "message": f"Resolution duration exceeds {IMPLAUSIBLE_DURATION_DAYS} days from ticket creation.",
        "recommended_action": "Review stale or reopened tickets separately; excluded from resolution-time metrics.",
    },
    {
        "code": "assignment_order_inconsistent",
        "severity": "warning",
        "affects": ["triage_metrics"],
        "message": "Assignment timestamp is before creation or after first response (or unparseable).",
        "recommended_action": "Audit manual queue-assignment timestamps; excluded from triage-lag metrics.",
    },
    {
        "code": "missing_assignment",
        "severity": "warning",
        "affects": ["triage_metrics"],
        "message": "Only one of assigned_at or assigned_agent is present on the ticket.",
        "recommended_action": "Ensure both assignment timestamp and assigned agent are exported; excluded from triage metrics.",
    },
    {
        "code": "resolved_at_on_unresolved_status",
        "severity": "warning",
        "affects": ["resolution_metrics"],
        "message": "Ticket status is open or pending, yet a resolved_at timestamp is populated.",
        "recommended_action": "Reconcile ticket status against resolution timestamps; excluded from resolution metrics.",
    },
    {
        "code": "unknown_status",
        "severity": "warning",
        "affects": [],
        "message": "Status value is outside the standard vocabulary (open, pending, resolved).",
        "recommended_action": "Review custom helpdesk statuses; downstream metrics will bucket these as unknown.",
    },
    {
        "code": "unknown_channel",
        "severity": "warning",
        "affects": [],
        "message": "Channel value is outside the standard vocabulary (email, chat, web_form, whatsapp).",
        "recommended_action": "Review custom intake channels; downstream metrics will bucket these as unknown.",
    },
    {
        "code": "unknown_priority",
        "severity": "warning",
        "affects": [],
        "message": "Priority value is outside the standard vocabulary (low, medium, high).",
        "recommended_action": "Standardise historical priority labels; downstream metrics will bucket these as unknown.",
    },
)

CHECK_BY_CODE: dict[str, dict[str, Any]] = {item["code"]: item for item in CHECK_DEFINITIONS}


@dataclass
class ValidatedRow:
    ticket_id: str
    created_at: datetime | None
    assigned_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    category: str | None
    priority: str | None
    queue: str | None
    assigned_agent: str | None
    status: str | None
    channel: str | None
    reassignment_count: int
    customer_id: str | None
    is_valid: bool
    validation_flags: list[dict[str, Any]]


@dataclass
class ValidationOutput:
    rows: list[ValidatedRow]
    record_count: int
    period_start: datetime | None
    period_end: datetime | None
    distinct_ticket_ids: int
    distinct_customers: int
    dataset_warnings: list[dict[str, Any]]
    checks: list[dict[str, Any]]
    rows_valid_for_all_metrics: int
    excluded_by_scope: dict[str, int]
    example_indices_by_code: dict[str, list[int]]


def _parse_iso_timestamp(raw_value: str) -> tuple[datetime | None, bool, bool]:
    """Parse an ISO 8601 timestamp into UTC.

    Returns (dt_utc, was_naive, is_invalid_non_empty).
    """
    if not raw_value:
        return None, False, False

    candidate = raw_value[:-1] + "+00:00" if raw_value.endswith(("Z", "z")) else raw_value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None, False, True

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=DEFAULT_TIMEZONE).astimezone(timezone.utc), True, False
    return parsed.astimezone(timezone.utc), False, False


def _parse_int_default_zero(raw_value: str) -> int:
    if not raw_value:
        return 0
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 0


def validate_parsed_csv(parsed: ParsedCSV, triage_config: TriageConfig) -> ValidationOutput:
    """Validate all rows deterministically without dropping any record."""
    valid_categories = {cat.id for cat in triage_config.categories}
    seen_ticket_ids: set[str] = set()

    validated_rows: list[ValidatedRow] = []
    naive_timestamp_count = 0

    check_counts: dict[str, int] = {item["code"]: 0 for item in CHECK_DEFINITIONS}
    example_indices: dict[str, list[int]] = {item["code"]: [] for item in CHECK_DEFINITIONS}

    valid_created_timestamps: list[datetime] = []
    distinct_customers: set[str] = set()
    distinct_ticket_ids: set[str] = set()

    excluded_all = 0
    excluded_response = 0
    excluded_resolution = 0
    excluded_triage = 0

    max_duration = timedelta(days=IMPLAUSIBLE_DURATION_DAYS)

    for row_index, raw in enumerate(parsed.rows):
        row_flags: list[dict[str, Any]] = []
        added_codes: set[str] = set()

        def _flag(code: str) -> None:
            if code in added_codes:
                return
            added_codes.add(code)
            defn = CHECK_BY_CODE[code]
            row_flags.append({"code": code, "affects": list(defn["affects"])})
            check_counts[code] += 1
            if len(example_indices[code]) < 5:
                example_indices[code].append(row_index)

        ticket_id = raw["ticket_id"]
        if ticket_id:
            distinct_ticket_ids.add(ticket_id)
            if ticket_id in seen_ticket_ids:
                _flag("duplicate_ticket_id")
            else:
                seen_ticket_ids.add(ticket_id)

        customer_id = raw["customer_id"]
        if customer_id:
            distinct_customers.add(customer_id)

        created_dt, c_naive, c_invalid = _parse_iso_timestamp(raw["created_at"])
        assigned_dt, a_naive, a_invalid = _parse_iso_timestamp(raw["assigned_at"])
        first_resp_dt, f_naive, f_invalid = _parse_iso_timestamp(raw["first_response_at"])
        resolved_dt, r_naive, r_invalid = _parse_iso_timestamp(raw["resolved_at"])

        naive_timestamp_count += int(c_naive) + int(a_naive) + int(f_naive) + int(r_naive)

        if created_dt is None or c_invalid:
            _flag("missing_or_invalid_created_at")
        else:
            valid_created_timestamps.append(created_dt)

        category = raw["category"]
        if category not in valid_categories:
            _flag("unknown_category")

        status = raw["status"]
        if status not in VALID_STATUSES:
            _flag("unknown_status")

        channel = raw["channel"]
        if channel not in VALID_CHANNELS:
            _flag("unknown_channel")

        priority = raw["priority"]
        if priority not in VALID_PRIORITIES:
            _flag("unknown_priority")

        # Response-metric checks
        frt_before_created = False
        if f_invalid:
            if status == "resolved":
                _flag("missing_first_response_on_resolved")
            else:
                _flag("first_response_before_created")
        elif first_resp_dt is not None and created_dt is not None and first_resp_dt < created_dt:
            frt_before_created = True
            _flag("first_response_before_created")

        if status == "resolved" and first_resp_dt is None:
            _flag("missing_first_response_on_resolved")

        # Resolution-metric checks
        if status == "resolved" and (resolved_dt is None or r_invalid):
            _flag("missing_resolved_at_on_resolved")

        if r_invalid and status != "resolved":
            _flag("resolved_before_created")

        if resolved_dt is not None and created_dt is not None:
            if resolved_dt < created_dt:
                _flag("resolved_before_created")
            elif (resolved_dt - created_dt) > max_duration:
                _flag("implausible_duration")

        if status in ("open", "pending") and (resolved_dt is not None or bool(raw["resolved_at"])):
            _flag("resolved_at_on_unresolved_status")

        # Triage-metric checks
        has_assigned_at = bool(raw["assigned_at"])
        has_assigned_agent = bool(raw["assigned_agent"])
        if has_assigned_at != has_assigned_agent:
            _flag("missing_assignment")

        if a_invalid:
            _flag("assignment_order_inconsistent")
        elif assigned_dt is not None:
            before_created = created_dt is not None and assigned_dt < created_dt
            after_valid_frt = (
                first_resp_dt is not None
                and not frt_before_created
                and assigned_dt > first_resp_dt
            )
            if before_created or after_valid_frt:
                _flag("assignment_order_inconsistent")

        affected_scopes: set[str] = set()
        for flag in row_flags:
            affected_scopes.update(flag["affects"])

        is_valid = "all_metrics" not in affected_scopes
        if not is_valid:
            excluded_all += 1
        if "all_metrics" in affected_scopes or "response_metrics" in affected_scopes:
            excluded_response += 1
        if "all_metrics" in affected_scopes or "resolution_metrics" in affected_scopes:
            excluded_resolution += 1
        if "all_metrics" in affected_scopes or "triage_metrics" in affected_scopes:
            excluded_triage += 1

        validated_rows.append(
            ValidatedRow(
                ticket_id=ticket_id,
                created_at=created_dt,
                assigned_at=assigned_dt,
                first_response_at=first_resp_dt,
                resolved_at=resolved_dt,
                category=category or None,
                priority=priority or None,
                queue=raw["queue"] or None,
                assigned_agent=raw["assigned_agent"] or None,
                status=status or None,
                channel=channel or None,
                reassignment_count=_parse_int_default_zero(raw["reassignment_count"]),
                customer_id=customer_id or None,
                is_valid=is_valid,
                validation_flags=row_flags,
            )
        )

    dataset_warnings: list[dict[str, Any]] = []
    if parsed.extra_columns:
        dataset_warnings.append(
            {
                "code": "extra_columns_ignored",
                "severity": "warning",
                "count": len(parsed.extra_columns),
                "columns": list(parsed.extra_columns),
                "message": (
                    f"Ignored {len(parsed.extra_columns)} unexpected column(s): "
                    f"{', '.join(parsed.extra_columns)}."
                ),
            }
        )
    if naive_timestamp_count > 0:
        dataset_warnings.append(
            {
                "code": "timestamps_without_timezone",
                "severity": "warning",
                "count": naive_timestamp_count,
                "assumed_timezone": "Asia/Kolkata",
                "message": (
                    f"{naive_timestamp_count} timestamp(s) had no timezone offset and were "
                    "interpreted as Asia/Kolkata (+05:30) before storing in UTC."
                ),
            }
        )

    checks_summary: list[dict[str, Any]] = []
    for defn in CHECK_DEFINITIONS:
        code = defn["code"]
        checks_summary.append(
            {
                "code": code,
                "severity": defn["severity"],
                "count": check_counts[code],
                "affects": list(defn["affects"]),
                "message": defn["message"],
                "recommended_action": defn["recommended_action"],
                "examples": [],
            }
        )

    record_count = len(validated_rows)
    return ValidationOutput(
        rows=validated_rows,
        record_count=record_count,
        period_start=min(valid_created_timestamps) if valid_created_timestamps else None,
        period_end=max(valid_created_timestamps) if valid_created_timestamps else None,
        distinct_ticket_ids=len(distinct_ticket_ids),
        distinct_customers=len(distinct_customers),
        dataset_warnings=dataset_warnings,
        checks=checks_summary,
        rows_valid_for_all_metrics=record_count - excluded_all,
        excluded_by_scope={
            "all_metrics": excluded_all,
            "response_metrics": excluded_response,
            "resolution_metrics": excluded_resolution,
            "triage_metrics": excluded_triage,
        },
        example_indices_by_code=example_indices,
    )
