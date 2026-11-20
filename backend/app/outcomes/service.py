"""Deterministic business logic for Outcomes: KPI baselines, target rules, and intervention scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.datasets import _get_active_dataset_id
from app.metrics.config import load_metrics_config
from app.metrics.frame import load_ticket_frame
from app.metrics.registry import compute_metric
from app.models import Dataset, Engagement, Intervention, Kpi
from app.outcomes.config import OutcomesConfig, load_outcomes_config


def compute_kpi_baseline(
    db: Session,
    dataset_id: int,
    metric_id: str,
) -> dict[str, Any]:
    """Compute deterministic baseline for a KPI from the metrics module on the given dataset."""
    cfg = load_outcomes_config()
    cat_item = next((item for item in cfg.kpi_catalogue if item.metric_id == metric_id), None)
    if cat_item is None:
        raise ValueError(f"Unknown metric_id: '{metric_id}'. Must be in KPI catalogue.")

    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found.")

    frame, as_of = load_ticket_frame(db, dataset_id)
    mcfg = load_metrics_config()
    res = compute_metric(metric_id, frame, config=mcfg, as_of=as_of)

    if metric_id in ("first_response_time", "triage_time", "resolution_time"):
        val = float(res.data.get("median", 0.0))
        n = int(res.data.get("n", 0))
    elif metric_id == "sla_attainment":
        rate = res.data.get("first_response", {}).get("attainment_rate")
        val = float(rate * 100.0) if rate is not None else 0.0
        n = int(res.data.get("first_response", {}).get("responded_n", 0))
    elif metric_id == "reassignment_rate":
        rate = res.data.get("overall", {}).get("rate")
        val = float(rate * 100.0) if rate is not None else 0.0
        n = int(res.data.get("overall", {}).get("n", 0))
    elif metric_id == "backlog_ageing":
        val = float(res.data.get("total_open_backlog", 0))
        n = int(res.n_included)
    else:
        raise ValueError(f"Unsupported KPI metric_id: {metric_id}")

    return {
        "value": round(val, 2),
        "unit": cat_item.unit,
        "n": n,
        "period_start": dataset.period_start.isoformat() if dataset.period_start else None,
        "period_end": dataset.period_end.isoformat() if dataset.period_end else None,
        "as_of": as_of.isoformat() if as_of else None,
        "dataset_id": dataset_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "metric_id": metric_id,
    }


def validate_kpi_target(
    direction: str,
    baseline_value: float,
    target_value: float | None,
    target_assumption: str | None,
) -> None:
    """Validate target assumption length and worsening-side guard."""
    if target_value is not None:
        if not target_assumption or len(target_assumption.strip()) < 10:
            raise ValueError("A target requires a target_assumption of at least 10 characters.")

        if direction == "lower_is_better" and target_value > baseline_value:
            raise ValueError(
                f"Target value ({target_value}) cannot be on the worsening side of baseline "
                f"({baseline_value}) for a lower-is-better metric."
            )
        if direction == "higher_is_better" and target_value < baseline_value:
            raise ValueError(
                f"Target value ({target_value}) cannot be on the worsening side of baseline "
                f"({baseline_value}) for a higher-is-better metric."
            )


def compute_planned_change(
    baseline_value: float,
    target_value: float | None,
) -> dict[str, Any] | None:
    """Compute planned change (target minus baseline). Never returns an improvement percentage."""
    if target_value is None:
        return None
    delta = round(target_value - baseline_value, 2)
    return {
        "value": delta,
        "label": "Planned change, not an outcome",
    }


def calculate_intervention_score(
    impact: int,
    effort: int,
    risk: int,
    weights: dict[str, float] | None = None,
) -> float:
    """Score = weight_impact * impact + weight_ease * (6 - effort) + weight_safety * (6 - risk)."""
    if weights is None:
        cfg = load_outcomes_config()
        weights = {
            "impact": cfg.prioritisation.weights.impact,
            "ease": cfg.prioritisation.weights.ease,
            "safety": cfg.prioritisation.weights.safety,
        }
    w_impact = weights.get("impact", 0.5)
    w_ease = weights.get("ease", 0.3)
    w_safety = weights.get("safety", 0.2)

    score = (
        w_impact * impact
        + w_ease * (6 - effort)
        + w_safety * (6 - risk)
    )
    return round(score, 2)


def seed_interventions_if_needed(db: Session, engagement_id: int) -> list[Intervention]:
    """Seed initial example interventions for engagement if none exist (idempotent)."""
    existing = db.scalars(
        select(Intervention)
        .where(Intervention.engagement_id == engagement_id)
    ).all()
    if existing:
        return sorted(existing, key=lambda i: calculate_intervention_score(i.impact, i.effort, i.risk), reverse=True)

    cfg = load_outcomes_config()
    seeded = []
    for s in cfg.seeded_interventions:
        inter = Intervention(
            engagement_id=engagement_id,
            name=s.name,
            description=s.description,
            impact=s.impact,
            effort=s.effort,
            risk=s.risk,
            rationale=s.rationale,
            status="proposed",
            origin="seeded",
        )
        db.add(inter)
        seeded.append(inter)

    db.commit()
    for item in seeded:
        db.refresh(item)
    return sorted(seeded, key=lambda i: calculate_intervention_score(i.impact, i.effort, i.risk), reverse=True)
