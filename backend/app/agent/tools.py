"""Pydantic-validated deterministic analysis tool registry for the investigation agent.

Tools wrap backend/app/metrics and backend/app/findings ONLY (R1, R4, R5).
Dataset and engagement binding happens server-side on ToolRunContext; tools
never accept dataset_id or engagement_id arguments and never return ticket rows (R6).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.findings.models import Finding, ValidationQuestion
from app.findings.rules import combine_validation_questions, generate_findings
from app.llm.base import ToolSchema
from app.metrics.config import ILLUSTRATIVE_SLA_NOTE, MetricsConfig, load_metrics_config
from app.metrics.frame import load_ticket_frame
from app.metrics.registry import compute_all_metrics
from app.metrics.results import MetricResult
from app.models import Dataset

MAX_TABLE_ROWS = 60


def round_nested(value: Any, decimals: int = 2) -> Any:
    """Round floats to a fixed precision while preserving ints, bools, strings, and None."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, list):
        return [round_nested(item, decimals) for item in value]
    if isinstance(value, dict):
        return {k: round_nested(v, decimals) for k, v in value.items()}
    return value


def _truncate_tables(
    obj: Any,
    max_rows: int = MAX_TABLE_ROWS,
) -> tuple[Any, bool, int | None]:
    """Recursively truncate any list of dict table rows exceeding max_rows."""
    if isinstance(obj, list):
        truncated = False
        original_count: int | None = None
        items = obj
        if len(obj) > max_rows and all(isinstance(el, dict) for el in obj):
            truncated = True
            original_count = len(obj)
            items = obj[:max_rows]
        new_items: list[Any] = []
        for item in items:
            child, child_trunc, child_orig = _truncate_tables(item, max_rows)
            new_items.append(child)
            if child_trunc:
                truncated = True
                if child_orig is not None and (
                    original_count is None or child_orig > original_count
                ):
                    original_count = child_orig
        return new_items, truncated, original_count

    if isinstance(obj, dict):
        truncated = False
        original_count = None
        new_dict: dict[str, Any] = {}
        for k, v in obj.items():
            child, child_trunc, child_orig = _truncate_tables(v, max_rows)
            new_dict[k] = child
            if child_trunc:
                truncated = True
                if child_orig is not None and (
                    original_count is None or child_orig > original_count
                ):
                    original_count = child_orig
        return new_dict, truncated, original_count

    return obj, False, None


class ToolError(BaseModel):
    """Structured error returned when a tool call fails validation or lookup."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ToolResult(BaseModel):
    """Normalized result envelope produced by every tool invocation."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool: str
    args: dict[str, Any]
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    error: ToolError | None = None
    duration_ms: int
    truncated: bool = False
    original_row_count: int | None = None


# ---------------------------------------------------------------------------
# Strict Pydantic argument models (extra="forbid", no dataset/engagement IDs)
# ---------------------------------------------------------------------------


class EmptyToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketSummaryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    volume_view: Literal["none", "by_day", "by_hour", "by_band", "by_channel"] = "none"


class ResponseMetricsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Literal[
        "first_response_time",
        "agent_response_time",
        "triage_time",
        "triage_share_of_first_response",
        "first_response_by_band",
        "sla_attainment",
        "factor_comparison",
    ]


class ResolutionMetricsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Literal["resolution_time"] = "resolution_time"


class CategoryBreakdownArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["volume", "delay_table", "reassignment"]


# ---------------------------------------------------------------------------
# Server-side bound run context & extensible ToolRegistry
# ---------------------------------------------------------------------------


@dataclass
class ToolRunContext:
    """Server-side context binding an investigation run to a single dataset."""

    db: Session
    engagement_id: int
    dataset: Dataset
    config: MetricsConfig = field(default_factory=load_metrics_config)
    _as_of: datetime | None = field(default=None, init=False, repr=False)
    _metrics: dict[str, MetricResult] | None = field(default=None, init=False, repr=False)
    _findings: list[Finding] | None = field(default=None, init=False, repr=False)
    _validation_questions: list[ValidationQuestion] | None = field(
        default=None, init=False, repr=False
    )

    def _ensure_computed(self) -> None:
        if self._metrics is not None:
            return
        frame, as_of = load_ticket_frame(self.db, self.dataset.id, self.config)
        self._as_of = as_of
        self._metrics = compute_all_metrics(frame, self.config, as_of)
        self._findings = generate_findings(self._metrics, self.config)
        self._validation_questions = combine_validation_questions(self._findings)

    @property
    def as_of(self) -> datetime | None:
        self._ensure_computed()
        return self._as_of

    @property
    def metrics(self) -> dict[str, MetricResult]:
        self._ensure_computed()
        assert self._metrics is not None
        return self._metrics

    @property
    def findings(self) -> list[Finding]:
        self._ensure_computed()
        assert self._findings is not None
        return self._findings

    @property
    def validation_questions(self) -> list[ValidationQuestion]:
        self._ensure_computed()
        assert self._validation_questions is not None
        return self._validation_questions


def _serialize_metric(result: MetricResult) -> dict[str, Any]:
    dumped = result.model_dump(mode="json")
    dumped["data"] = round_nested(dumped["data"], 2)
    return dumped


def _serialize_finding(finding: Finding) -> dict[str, Any]:
    dumped = finding.model_dump(mode="json")
    for ev in dumped.get("evidence", []):
        ev["value"] = round_nested(ev.get("value"), 2)
    return dumped


def _build_kpi_summaries(ctx: ToolRunContext) -> list[dict[str, Any]]:
    metrics = ctx.metrics
    frt = metrics["first_response_time"]
    triage = metrics["triage_time"]
    res = metrics["resolution_time"]
    sla = metrics["sla_attainment"]
    backlog = metrics["backlog_ageing"]
    reassign = metrics["reassignment_rate"]

    frt_sla_rate = sla.data["first_response"]["attainment_rate"]
    frt_sla_pct = round(frt_sla_rate * 100.0, 2) if frt_sla_rate is not None else None
    reassign_rate_val = reassign.data["overall"]["rate"]
    reassign_pct = (
        round(reassign_rate_val * 100.0, 2) if reassign_rate_val is not None else None
    )

    period_start = (
        ctx.dataset.period_start.isoformat() if ctx.dataset.period_start else None
    )
    period_end = ctx.dataset.period_end.isoformat() if ctx.dataset.period_end else None

    return [
        {
            "metric_id": "first_response_time",
            "name": "Median first-response time",
            "value": round_nested(frt.data["median"], 2),
            "unit": "hours",
            "period_start": period_start,
            "period_end": period_end,
            "n": int(frt.data["n"]),
            "definition": frt.definition,
            "scope": frt.scope,
            "n_excluded": frt.n_excluded,
            "exclusions": dict(frt.exclusions),
            "note": None,
        },
        {
            "metric_id": "triage_time",
            "name": "Median time to assignment",
            "value": round_nested(triage.data["median"], 2),
            "unit": "hours",
            "period_start": period_start,
            "period_end": period_end,
            "n": int(triage.data["n"]),
            "definition": triage.definition,
            "scope": triage.scope,
            "n_excluded": triage.n_excluded,
            "exclusions": dict(triage.exclusions),
            "note": None,
        },
        {
            "metric_id": "resolution_time",
            "name": "Median resolution time",
            "value": round_nested(res.data["median"], 2),
            "unit": "hours",
            "period_start": period_start,
            "period_end": period_end,
            "n": int(res.data["n"]),
            "definition": res.definition,
            "scope": res.scope,
            "n_excluded": res.n_excluded,
            "exclusions": dict(res.exclusions),
            "note": None,
        },
        {
            "metric_id": "sla_attainment",
            "name": "First-response SLA attainment",
            "value": frt_sla_pct,
            "unit": "%",
            "period_start": period_start,
            "period_end": period_end,
            "n": int(sla.data["first_response"]["responded_n"]),
            "definition": sla.definition,
            "scope": sla.scope,
            "n_excluded": sla.n_excluded,
            "exclusions": dict(sla.exclusions),
            "note": ILLUSTRATIVE_SLA_NOTE,
        },
        {
            "metric_id": "backlog_ageing",
            "name": "Open backlog at as-of",
            "value": int(backlog.data["total_open_backlog"]),
            "unit": "tickets",
            "period_start": period_start,
            "period_end": period_end,
            "n": backlog.n_included,
            "definition": backlog.definition,
            "scope": backlog.scope,
            "n_excluded": backlog.n_excluded,
            "exclusions": dict(backlog.exclusions),
            "note": None,
        },
        {
            "metric_id": "reassignment_rate",
            "name": "Overall reassignment rate",
            "value": reassign_pct,
            "unit": "%",
            "period_start": period_start,
            "period_end": period_end,
            "n": int(reassign.data["overall"]["n"]),
            "definition": reassign.definition,
            "scope": reassign.scope,
            "n_excluded": reassign.n_excluded,
            "exclusions": dict(reassign.exclusions),
            "note": None,
        },
    ]


def _build_scope_summary(ctx: ToolRunContext) -> dict[str, Any]:
    metrics = ctx.metrics
    vol_all = metrics["volume_by_category"]
    return {
        "total_rows": ctx.dataset.record_count,
        "rows_valid_for_all_metrics": vol_all.n_included,
        "excluded_by_scope": {
            "all_metrics": vol_all.n_excluded,
            "response_metrics": metrics["first_response_time"].n_excluded,
            "resolution_metrics": metrics["resolution_time"].n_excluded,
            "triage_metrics": metrics["triage_time"].n_excluded,
        },
    }


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _handle_get_ticket_summary(
    ctx: ToolRunContext, args: TicketSummaryArgs
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "dataset": {
            "filename": ctx.dataset.filename,
            "is_sample": ctx.dataset.is_sample,
            "record_count": ctx.dataset.record_count,
            "period_start": (
                ctx.dataset.period_start.isoformat() if ctx.dataset.period_start else None
            ),
            "period_end": (
                ctx.dataset.period_end.isoformat() if ctx.dataset.period_end else None
            ),
        },
        "as_of": ctx.as_of.isoformat() if ctx.as_of else None,
        "timezone": ctx.config.timezone,
        "scope_summary": _build_scope_summary(ctx),
        "kpis": _build_kpi_summaries(ctx),
    }
    volume_map = {
        "by_day": "volume_by_day",
        "by_hour": "volume_by_hour",
        "by_band": "volume_by_band",
        "by_channel": "volume_by_channel",
    }
    if args.volume_view != "none":
        metric_id = volume_map[args.volume_view]
        payload["volume_view"] = _serialize_metric(ctx.metrics[metric_id])
    return payload


def _handle_get_response_metrics(
    ctx: ToolRunContext, args: ResponseMetricsArgs
) -> dict[str, Any]:
    return _serialize_metric(ctx.metrics[args.metric])


def _handle_get_resolution_metrics(
    ctx: ToolRunContext, args: ResolutionMetricsArgs
) -> dict[str, Any]:
    return _serialize_metric(ctx.metrics[args.metric])


def _handle_get_category_breakdown(
    ctx: ToolRunContext, args: CategoryBreakdownArgs
) -> dict[str, Any]:
    metric_map = {
        "volume": "volume_by_category",
        "delay_table": "category_delay_table",
        "reassignment": "reassignment_rate",
    }
    return _serialize_metric(ctx.metrics[metric_map[args.view]])


def _handle_get_agent_workload(
    ctx: ToolRunContext, _args: EmptyToolArgs
) -> dict[str, Any]:
    return _serialize_metric(ctx.metrics["agent_workload"])


def _handle_get_backlog_analysis(
    ctx: ToolRunContext, _args: EmptyToolArgs
) -> dict[str, Any]:
    return _serialize_metric(ctx.metrics["backlog_ageing"])


def _handle_get_findings(
    ctx: ToolRunContext, _args: EmptyToolArgs
) -> dict[str, Any]:
    return {
        "scope_summary": _build_scope_summary(ctx),
        "findings": [_serialize_finding(f) for f in ctx.findings],
        "validation_questions": [
            q.model_dump(mode="json") for q in ctx.validation_questions
        ],
    }


@dataclass(frozen=True)
class ToolSpec:
    """Declarative specification for one agent tool."""

    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolRunContext, Any], dict[str, Any]]

    def to_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters_schema=self.args_model.model_json_schema(),
        )


class ToolRegistry:
    """Extensible registry executing Pydantic-validated tools for a single run."""

    def __init__(
        self,
        context: ToolRunContext,
        *,
        max_table_rows: int = MAX_TABLE_ROWS,
    ) -> None:
        self._context = context
        self._max_table_rows = max_table_rows
        self._specs: dict[str, ToolSpec] = {}
        self._call_counter = 0

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    @property
    def tool_names(self) -> list[str]:
        return list(self._specs.keys())

    def schemas(self) -> list[ToolSchema]:
        return [spec.to_schema() for spec in self._specs.values()]

    def _next_call_id(self) -> str:
        self._call_counter += 1
        return f"c{self._call_counter}"

    def execute(self, tool_name: str, raw_args: dict[str, Any] | None = None) -> ToolResult:
        """Validate arguments, invoke the bound tool, and always return a ToolResult."""
        call_id = self._next_call_id()
        started = time.perf_counter()
        supplied_args = raw_args if isinstance(raw_args, dict) else {}

        spec = self._specs.get(tool_name)
        if spec is None:
            elapsed = int(round((time.perf_counter() - started) * 1000))
            return ToolResult(
                call_id=call_id,
                tool=tool_name,
                args=supplied_args,
                ok=False,
                data=None,
                error=ToolError(
                    code="unknown_tool",
                    message=(
                        f"Unknown tool '{tool_name}'. Available tools: "
                        + ", ".join(self._specs.keys())
                        + "."
                    ),
                ),
                duration_ms=elapsed,
            )

        if raw_args is not None and not isinstance(raw_args, dict):
            elapsed = int(round((time.perf_counter() - started) * 1000))
            return ToolResult(
                call_id=call_id,
                tool=tool_name,
                args={},
                ok=False,
                data=None,
                error=ToolError(
                    code="invalid_arguments",
                    message="Tool arguments must be a JSON object.",
                ),
                duration_ms=elapsed,
            )

        try:
            validated = spec.args_model.model_validate(supplied_args)
        except ValidationError as exc:
            elapsed = int(round((time.perf_counter() - started) * 1000))
            first_errors = "; ".join(
                f"{'.'.join(str(p) for p in err.get('loc', ())) or 'args'}: {err.get('msg', 'invalid')}"
                for err in exc.errors()[:3]
            )
            return ToolResult(
                call_id=call_id,
                tool=tool_name,
                args=supplied_args,
                ok=False,
                data=None,
                error=ToolError(
                    code="invalid_arguments",
                    message=f"Invalid arguments for '{tool_name}': {first_errors}",
                ),
                duration_ms=elapsed,
            )

        try:
            raw_data = spec.handler(self._context, validated)
            truncated_data, was_truncated, orig_count = _truncate_tables(
                raw_data, max_rows=self._max_table_rows
            )
            elapsed = int(round((time.perf_counter() - started) * 1000))
            return ToolResult(
                call_id=call_id,
                tool=tool_name,
                args=validated.model_dump(mode="json"),
                ok=True,
                data=truncated_data,
                error=None,
                duration_ms=elapsed,
                truncated=was_truncated,
                original_row_count=orig_count,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            elapsed = int(round((time.perf_counter() - started) * 1000))
            return ToolResult(
                call_id=call_id,
                tool=tool_name,
                args=validated.model_dump(mode="json"),
                ok=False,
                data=None,
                error=ToolError(
                    code="tool_execution_error",
                    message=f"Tool '{tool_name}' failed: {exc}",
                ),
                duration_ms=elapsed,
            )


ANALYSIS_TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_ticket_summary",
        description=(
            "Return dataset metadata, as-of timestamp, validation scope exclusions, "
            "the six baseline operational KPIs, and an optional volume distribution "
            "(none, by_day, by_hour, by_band, by_channel)."
        ),
        args_model=TicketSummaryArgs,
        handler=_handle_get_ticket_summary,
    ),
    ToolSpec(
        name="get_response_metrics",
        description=(
            "Return one deterministic response-timing metric with definition, scope, "
            "n_included, n_excluded, and exclusions: first_response_time, "
            "agent_response_time, triage_time, triage_share_of_first_response, "
            "first_response_by_band, sla_attainment, or factor_comparison."
        ),
        args_model=ResponseMetricsArgs,
        handler=_handle_get_response_metrics,
    ),
    ToolSpec(
        name="get_resolution_metrics",
        description=(
            "Return the deterministic resolution_time metric (median, p90, mean, "
            "definition, scope, n, and exclusions)."
        ),
        args_model=ResolutionMetricsArgs,
        handler=_handle_get_resolution_metrics,
    ),
    ToolSpec(
        name="get_category_breakdown",
        description=(
            "Return category-level aggregates: volume (counts & shares), "
            "delay_table (median triage/FRT/resolution and reassignment per category), "
            "or reassignment (overall and per-category reassignment rates)."
        ),
        args_model=CategoryBreakdownArgs,
        handler=_handle_get_category_breakdown,
    ),
    ToolSpec(
        name="get_agent_workload",
        description=(
            "Return agent ticket workload distribution, top-3 agent share, "
            "unassigned count, and Gini concentration coefficient."
        ),
        args_model=EmptyToolArgs,
        handler=_handle_get_agent_workload,
    ),
    ToolSpec(
        name="get_backlog_analysis",
        description=(
            "Return open/pending backlog count at dataset as-of, oldest ticket age "
            "in days, and ageing bucket counts (<1d, 1-3d, 3-7d, 7d+)."
        ),
        args_model=EmptyToolArgs,
        handler=_handle_get_backlog_analysis,
    ),
    ToolSpec(
        name="get_findings",
        description=(
            "Return the deterministic rule-based diagnostic findings with evidence, "
            "limitations, and template validation questions."
        ),
        args_model=EmptyToolArgs,
        handler=_handle_get_findings,
    ),
)


def build_analysis_tool_registry(
    context: ToolRunContext,
    *,
    max_table_rows: int = MAX_TABLE_ROWS,
) -> ToolRegistry:
    """Create a ToolRegistry populated with the seven read-only analysis tools."""
    registry = ToolRegistry(context, max_table_rows=max_table_rows)
    for spec in ANALYSIS_TOOL_SPECS:
        registry.register(spec)
    return registry
