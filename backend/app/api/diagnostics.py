"""Read-only diagnostics analysis endpoint computing deterministic KPIs, metrics, and findings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.datasets import _get_active_dataset_id, _get_dataset_or_404
from app.db import get_db
from app.findings.models import Finding, ValidationQuestion
from app.findings.rules import combine_validation_questions, generate_findings
from app.metrics.config import ILLUSTRATIVE_SLA_NOTE, load_metrics_config
from app.metrics.frame import load_ticket_frame
from app.metrics.registry import compute_all_metrics
from app.metrics.results import MetricResult

router = APIRouter(
    prefix="/api/engagements/{engagement_id}/datasets/{dataset_id}/diagnostics",
    tags=["diagnostics"],
)


def _round_value(value: Any, decimals: int = 2) -> Any:
    """Round floats only at serialization time; preserve ints, strings, bools, and None."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, list):
        return [_round_value(item, decimals) for item in value]
    if isinstance(value, dict):
        return {k: _round_value(v, decimals) for k, v in value.items()}
    return value


def _round_metric_result(result: MetricResult) -> MetricResult:
    return result.model_copy(update={"data": _round_value(result.data, 2)})


def _round_finding(finding: Finding) -> Finding:
    rounded_evidence = [
        ev.model_copy(update={"value": _round_value(ev.value, 2)})
        for ev in finding.evidence
    ]
    return finding.model_copy(update={"evidence": rounded_evidence})


class DiagnosticsDatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    filename: str
    is_sample: bool
    is_active: bool
    uploaded_at: datetime
    record_count: int
    period_start: datetime | None
    period_end: datetime | None


class DiagnosticsKpi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    name: str
    value: float | int | None
    unit: str
    period_start: datetime | None
    period_end: datetime | None
    n: int
    definition: str
    scope: str
    n_excluded: int
    exclusions: dict[str, int]
    note: str | None = None


class DiagnosticsScopeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_rows: int
    rows_valid_for_all_metrics: int
    excluded_by_scope: dict[str, int]


class DiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: DiagnosticsDatasetSummary
    as_of: datetime | None
    timezone: str
    scope_summary: DiagnosticsScopeSummary
    kpis: list[DiagnosticsKpi]
    metrics: dict[str, MetricResult]
    findings: list[Finding]
    validation_questions: list[ValidationQuestion]


def _build_kpis(
    metrics: dict[str, MetricResult],
    period_start: datetime | None,
    period_end: datetime | None,
) -> list[DiagnosticsKpi]:
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

    return [
        DiagnosticsKpi(
            metric_id="first_response_time",
            name="Median first-response time",
            value=_round_value(frt.data["median"], 2),
            unit="hours",
            period_start=period_start,
            period_end=period_end,
            n=int(frt.data["n"]),
            definition=frt.definition,
            scope=frt.scope,
            n_excluded=frt.n_excluded,
            exclusions=dict(frt.exclusions),
        ),
        DiagnosticsKpi(
            metric_id="triage_time",
            name="Median time to assignment",
            value=_round_value(triage.data["median"], 2),
            unit="hours",
            period_start=period_start,
            period_end=period_end,
            n=int(triage.data["n"]),
            definition=triage.definition,
            scope=triage.scope,
            n_excluded=triage.n_excluded,
            exclusions=dict(triage.exclusions),
        ),
        DiagnosticsKpi(
            metric_id="resolution_time",
            name="Median resolution time",
            value=_round_value(res.data["median"], 2),
            unit="hours",
            period_start=period_start,
            period_end=period_end,
            n=int(res.data["n"]),
            definition=res.definition,
            scope=res.scope,
            n_excluded=res.n_excluded,
            exclusions=dict(res.exclusions),
        ),
        DiagnosticsKpi(
            metric_id="sla_attainment",
            name="First-response SLA attainment",
            value=frt_sla_pct,
            unit="%",
            period_start=period_start,
            period_end=period_end,
            n=int(sla.data["first_response"]["responded_n"]),
            definition=sla.definition,
            scope=sla.scope,
            n_excluded=sla.n_excluded,
            exclusions=dict(sla.exclusions),
            note=ILLUSTRATIVE_SLA_NOTE,
        ),
        DiagnosticsKpi(
            metric_id="backlog_ageing",
            name="Open backlog at as-of",
            value=int(backlog.data["total_open_backlog"]),
            unit="tickets",
            period_start=period_start,
            period_end=period_end,
            n=backlog.n_included,
            definition=backlog.definition,
            scope=backlog.scope,
            n_excluded=backlog.n_excluded,
            exclusions=dict(backlog.exclusions),
        ),
        DiagnosticsKpi(
            metric_id="reassignment_rate",
            name="Overall reassignment rate",
            value=reassign_pct,
            unit="%",
            period_start=period_start,
            period_end=period_end,
            n=int(reassign.data["overall"]["n"]),
            definition=reassign.definition,
            scope=reassign.scope,
            n_excluded=reassign.n_excluded,
            exclusions=dict(reassign.exclusions),
        ),
    ]


@router.get("", response_model=DiagnosticsResponse)
def get_diagnostics(
    engagement_id: int,
    dataset_id: int,
    db: Session = Depends(get_db),
) -> DiagnosticsResponse:
    """Compute deterministic KPIs, metrics, and rule-based findings for a stored dataset."""
    dataset = _get_dataset_or_404(db, engagement_id, dataset_id)
    active_id = _get_active_dataset_id(db, engagement_id)

    config = load_metrics_config()
    frame, as_of = load_ticket_frame(db, dataset.id, config)
    raw_metrics = compute_all_metrics(frame, config, as_of)
    raw_findings = generate_findings(raw_metrics, config)
    validation_questions = combine_validation_questions(raw_findings)

    kpis = _build_kpis(raw_metrics, dataset.period_start, dataset.period_end)
    rounded_metrics = {
        mid: _round_metric_result(res) for mid, res in raw_metrics.items()
    }
    rounded_findings = [_round_finding(f) for f in raw_findings]

    vol_all = raw_metrics["volume_by_category"]
    scope_summary = DiagnosticsScopeSummary(
        total_rows=dataset.record_count,
        rows_valid_for_all_metrics=vol_all.n_included,
        excluded_by_scope={
            "all_metrics": vol_all.n_excluded,
            "response_metrics": raw_metrics["first_response_time"].n_excluded,
            "resolution_metrics": raw_metrics["resolution_time"].n_excluded,
            "triage_metrics": raw_metrics["triage_time"].n_excluded,
        },
    )

    return DiagnosticsResponse(
        dataset=DiagnosticsDatasetSummary(
            id=dataset.id,
            engagement_id=dataset.engagement_id,
            filename=dataset.filename,
            is_sample=dataset.is_sample,
            is_active=(dataset.id == active_id),
            uploaded_at=dataset.uploaded_at,
            record_count=dataset.record_count,
            period_start=dataset.period_start,
            period_end=dataset.period_end,
        ),
        as_of=as_of,
        timezone=config.timezone,
        scope_summary=scope_summary,
        kpis=kpis,
        metrics=rounded_metrics,
        findings=rounded_findings,
        validation_questions=validation_questions,
    )
