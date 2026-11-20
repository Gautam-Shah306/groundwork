"""REST API endpoints for the Outcomes stage (KPIs, interventions, simulation, review)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.datasets import _get_active_dataset_id
from app.api.engagements import get_engagement_or_404
from app.audit import record_audit_event
from app.config import Settings, get_settings
from app.db import get_db
from app.llm.base import LLMProvider
from app.llm.errors import LLMError, LLMRateLimited, LLMOutputTruncated
from app.llm.factory import get_provider
from app.metrics.frame import load_ticket_frame, scope
from app.models import (
    Dataset,
    Engagement,
    EvalRun,
    EvalRunStatus,
    Intervention,
    Kpi,
    OutcomeReview,
    PilotSimulation,
)
from app.outcomes.config import OutcomesConfig, load_outcomes_config
from app.outcomes.review import (
    build_review_snapshot,
    draft_outcome_review,
    postprocess_outcome_review,
)
from app.outcomes.service import (
    calculate_intervention_score,
    compute_kpi_baseline,
    compute_planned_change,
    seed_interventions_if_needed,
    validate_kpi_target,
)
from app.outcomes.simulation import run_pilot_simulation

router = APIRouter(prefix="/api/engagements/{engagement_id}/outcomes", tags=["outcomes"])


def _resolve_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, Settings):
        return configured
    return get_settings()


def _resolve_provider(request: Request, settings: Settings) -> LLMProvider:
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is not None:
        return provider
    return get_provider(settings)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KpiCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    name: str | None = None
    target_value: float | None = None
    target_assumption: str | None = None
    is_primary: bool = False


class KpiUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    target_value: float | None = None
    target_assumption: str | None = None
    is_primary: bool | None = None


class KpiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    metric_id: str
    name: str
    definition: str
    calculation: str
    unit: str
    direction: str
    baseline: dict[str, Any] | None
    target_value: float | None
    target_assumption: str | None
    planned_change: dict[str, Any] | None
    is_primary: bool
    is_stale: bool
    status: str


class InterventionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    impact: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    risk: int = Field(ge=1, le=5)
    rationale: str = ""
    status: Literal["proposed", "selected", "rejected"] = "proposed"


class InterventionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    impact: int | None = Field(default=None, ge=1, le=5)
    effort: int | None = Field(default=None, ge=1, le=5)
    risk: int | None = Field(default=None, ge=1, le=5)
    rationale: str | None = None
    status: Literal["proposed", "selected", "rejected"] | None = None


class InterventionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    name: str
    description: str
    impact: int
    effort: int
    risk: int
    score: float
    rationale: str
    status: str
    origin: str
    created_at: datetime
    updated_at: datetime


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_share: float = Field(default=0.5, ge=0.2, le=0.8)
    reduction_pct: float = Field(default=50.0, ge=0.0, le=90.0)
    adoption_pct: float = Field(default=80.0, ge=0.0, le=100.0)
    rework_share: float | None = Field(default=None, ge=0.0, le=1.0)
    seed: int = 42


class OutcomeReviewUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: dict[str, Any]


class OutcomeReviewDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_replace: bool = False


class OutcomeReviewConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_recommendation: Literal["continue", "modify", "expand", "stop"]
    acknowledged_simulated: bool


# ---------------------------------------------------------------------------
# KPI Endpoints
# ---------------------------------------------------------------------------


@router.get("/kpi-catalogue")
def get_kpi_catalogue(engagement_id: int) -> list[dict[str, Any]]:
    """Return catalogue of supported outcomes KPIs."""
    cfg = load_outcomes_config()
    return [item.model_dump() for item in cfg.kpi_catalogue]


@router.get("/kpis")
def list_kpis(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[KpiResponse]:
    """List all KPIs for an engagement, with computed staleness and planned change."""
    get_engagement_or_404(db, engagement_id)
    active_dataset_id = _get_active_dataset_id(db, engagement_id)

    kpis = db.scalars(
        select(Kpi)
        .where(Kpi.engagement_id == engagement_id)
        .order_by(Kpi.is_primary.desc(), Kpi.id.asc())
    ).all()

    responses: list[KpiResponse] = []
    for k in kpis:
        base_val = k.baseline.get("value") if k.baseline else None
        p_change = (
            compute_planned_change(base_val, k.target_value)
            if base_val is not None and k.target_value is not None
            else None
        )
        is_stale = (
            k.baseline_dataset_id != active_dataset_id
            if active_dataset_id is not None
            else True
        )
        responses.append(
            KpiResponse(
                id=k.id,
                engagement_id=k.engagement_id,
                metric_id=k.metric_id,
                name=k.name,
                definition=k.definition,
                calculation=k.calculation,
                unit=k.baseline.get("unit", "") if k.baseline else "",
                direction=k.direction,
                baseline=k.baseline,
                target_value=k.target_value,
                target_assumption=k.target_assumption,
                planned_change=p_change,
                is_primary=k.is_primary,
                is_stale=is_stale,
                status=k.status,
            )
        )
    return responses


@router.post("/kpis", status_code=status.HTTP_201_CREATED)
def create_kpi(
    engagement_id: int,
    payload: KpiCreateRequest,
    db: Session = Depends(get_db),
) -> KpiResponse:
    """Create a new KPI with deterministically computed baseline from active dataset."""
    get_engagement_or_404(db, engagement_id)
    cfg = load_outcomes_config()
    cat_item = next(
        (item for item in cfg.kpi_catalogue if item.metric_id == payload.metric_id),
        None,
    )
    if cat_item is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown metric_id '{payload.metric_id}'. Must be in KPI catalogue.",
        )

    active_dataset_id = _get_active_dataset_id(db, engagement_id)
    if active_dataset_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Engagement has no active dataset. Upload or select a dataset before adding KPIs.",
        )

    try:
        baseline_data = compute_kpi_baseline(db, active_dataset_id, payload.metric_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to compute baseline for {payload.metric_id}: {exc}",
        ) from exc

    # Validate target if supplied
    base_val = float(baseline_data["value"])
    if payload.target_value is not None:
        try:
            validate_kpi_target(
                cat_item.direction,
                base_val,
                payload.target_value,
                payload.target_assumption,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    # If setting this KPI as primary, clear any existing primary KPI
    if payload.is_primary:
        existing_primaries = db.scalars(
            select(Kpi).where(Kpi.engagement_id == engagement_id, Kpi.is_primary == True)
        ).all()
        for ep in existing_primaries:
            ep.is_primary = False

    kpi = Kpi(
        engagement_id=engagement_id,
        name=payload.name or cat_item.name,
        definition=cat_item.description,
        calculation=f"Deterministic calculation of {cat_item.metric_id}",
        baseline=baseline_data,
        target=str(payload.target_value) if payload.target_value is not None else None,
        target_assumption=payload.target_assumption,
        is_primary=payload.is_primary,
        metric_id=payload.metric_id,
        direction=cat_item.direction,
        baseline_dataset_id=active_dataset_id,
        target_value=payload.target_value,
        status="active",
    )
    db.add(kpi)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="kpi_created",
        entity_type="kpi",
        entity_id=str(kpi.id),
        details={"metric_id": kpi.metric_id, "kpi_id": kpi.id, "is_primary": kpi.is_primary},
    )
    db.commit()
    db.refresh(kpi)

    p_change = (
        compute_planned_change(base_val, kpi.target_value)
        if kpi.target_value is not None
        else None
    )

    return KpiResponse(
        id=kpi.id,
        engagement_id=kpi.engagement_id,
        metric_id=kpi.metric_id,
        name=kpi.name,
        definition=kpi.definition,
        calculation=kpi.calculation,
        unit=kpi.baseline.get("unit", "") if kpi.baseline else "",
        direction=kpi.direction,
        baseline=kpi.baseline,
        target_value=kpi.target_value,
        target_assumption=kpi.target_assumption,
        planned_change=p_change,
        is_primary=kpi.is_primary,
        is_stale=False,
        status=kpi.status,
    )


@router.patch("/kpis/{kpi_id}")
def update_kpi(
    engagement_id: int,
    kpi_id: int,
    payload: KpiUpdateRequest,
    db: Session = Depends(get_db),
) -> KpiResponse:
    """Update target or primary status of a KPI."""
    get_engagement_or_404(db, engagement_id)
    kpi = db.get(Kpi, kpi_id)
    if kpi is None or kpi.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found.")

    if payload.name is not None:
        kpi.name = payload.name

    new_target_val = payload.target_value if payload.target_value is not None else kpi.target_value
    new_assumption = (
        payload.target_assumption
        if payload.target_assumption is not None
        else kpi.target_assumption
    )

    base_val = kpi.baseline.get("value", 0.0) if kpi.baseline else 0.0
    if payload.target_value is not None or payload.target_assumption is not None:
        try:
            validate_kpi_target(
                kpi.direction,
                base_val,
                new_target_val,
                new_assumption,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        kpi.target_value = new_target_val
        kpi.target_assumption = new_assumption
        kpi.target = str(new_target_val) if new_target_val is not None else None

    if payload.is_primary is not None:
        if payload.is_primary:
            existing_primaries = db.scalars(
                select(Kpi).where(
                    Kpi.engagement_id == engagement_id,
                    Kpi.is_primary == True,
                    Kpi.id != kpi.id,
                )
            ).all()
            for ep in existing_primaries:
                ep.is_primary = False
        kpi.is_primary = payload.is_primary

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="kpi_updated",
        entity_type="kpi",
        entity_id=str(kpi.id),
        details={"metric_id": kpi.metric_id, "kpi_id": kpi.id, "is_primary": kpi.is_primary},
    )
    db.commit()
    db.refresh(kpi)

    active_dataset_id = _get_active_dataset_id(db, engagement_id)
    is_stale = (
        kpi.baseline_dataset_id != active_dataset_id
        if active_dataset_id is not None
        else True
    )
    p_change = (
        compute_planned_change(base_val, kpi.target_value)
        if kpi.target_value is not None
        else None
    )

    return KpiResponse(
        id=kpi.id,
        engagement_id=kpi.engagement_id,
        metric_id=kpi.metric_id,
        name=kpi.name,
        definition=kpi.definition,
        calculation=kpi.calculation,
        unit=kpi.baseline.get("unit", "") if kpi.baseline else "",
        direction=kpi.direction,
        baseline=kpi.baseline,
        target_value=kpi.target_value,
        target_assumption=kpi.target_assumption,
        planned_change=p_change,
        is_primary=kpi.is_primary,
        is_stale=is_stale,
        status=kpi.status,
    )


@router.delete("/kpis/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kpi(
    engagement_id: int,
    kpi_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a KPI."""
    get_engagement_or_404(db, engagement_id)
    kpi = db.get(Kpi, kpi_id)
    if kpi is None or kpi.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found.")

    m_id = kpi.metric_id
    db.delete(kpi)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="kpi_deleted",
        entity_type="kpi",
        entity_id=str(kpi_id),
        details={"metric_id": m_id, "kpi_id": kpi_id},
    )
    db.commit()


@router.post("/kpis/{kpi_id}/recompute-baseline")
def recompute_kpi_baseline(
    engagement_id: int,
    kpi_id: int,
    db: Session = Depends(get_db),
) -> KpiResponse:
    """Recompute KPI baseline against the current active dataset."""
    get_engagement_or_404(db, engagement_id)
    kpi = db.get(Kpi, kpi_id)
    if kpi is None or kpi.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found.")

    active_dataset_id = _get_active_dataset_id(db, engagement_id)
    if active_dataset_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Engagement has no active dataset.",
        )

    try:
        baseline_data = compute_kpi_baseline(db, active_dataset_id, kpi.metric_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to recompute baseline: {exc}",
        ) from exc

    kpi.baseline = baseline_data
    kpi.baseline_dataset_id = active_dataset_id

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="kpi_baseline_recomputed",
        entity_type="kpi",
        entity_id=str(kpi.id),
        details={"metric_id": kpi.metric_id, "kpi_id": kpi.id, "dataset_id": active_dataset_id},
    )
    db.commit()
    db.refresh(kpi)

    base_val = float(baseline_data["value"])
    p_change = (
        compute_planned_change(base_val, kpi.target_value)
        if kpi.target_value is not None
        else None
    )

    return KpiResponse(
        id=kpi.id,
        engagement_id=kpi.engagement_id,
        metric_id=kpi.metric_id,
        name=kpi.name,
        definition=kpi.definition,
        calculation=kpi.calculation,
        unit=kpi.baseline.get("unit", "") if kpi.baseline else "",
        direction=kpi.direction,
        baseline=kpi.baseline,
        target_value=kpi.target_value,
        target_assumption=kpi.target_assumption,
        planned_change=p_change,
        is_primary=kpi.is_primary,
        is_stale=False,
        status=kpi.status,
    )


# ---------------------------------------------------------------------------
# Interventions Endpoints
# ---------------------------------------------------------------------------


@router.get("/interventions")
def list_interventions(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[InterventionResponse]:
    """List all interventions sorted by score descending, seeding defaults on first access."""
    get_engagement_or_404(db, engagement_id)
    items = seed_interventions_if_needed(db, engagement_id)
    return [
        InterventionResponse(
            id=i.id,
            engagement_id=i.engagement_id,
            name=i.name,
            description=i.description,
            impact=i.impact,
            effort=i.effort,
            risk=i.risk,
            score=calculate_intervention_score(i.impact, i.effort, i.risk),
            rationale=i.rationale,
            status=i.status,
            origin=i.origin,
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in items
    ]


@router.post("/interventions", status_code=status.HTTP_201_CREATED)
def create_intervention(
    engagement_id: int,
    payload: InterventionCreateRequest,
    db: Session = Depends(get_db),
) -> InterventionResponse:
    """Create a human operator intervention."""
    get_engagement_or_404(db, engagement_id)
    inter = Intervention(
        engagement_id=engagement_id,
        name=payload.name,
        description=payload.description,
        impact=payload.impact,
        effort=payload.effort,
        risk=payload.risk,
        rationale=payload.rationale,
        status=payload.status,
        origin="human",
    )
    db.add(inter)
    db.flush()

    score = calculate_intervention_score(inter.impact, inter.effort, inter.risk)
    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="intervention_created",
        entity_type="intervention",
        entity_id=str(inter.id),
        details={"name": inter.name, "score": score, "origin": "human"},
    )
    db.commit()
    db.refresh(inter)

    return InterventionResponse(
        id=inter.id,
        engagement_id=inter.engagement_id,
        name=inter.name,
        description=inter.description,
        impact=inter.impact,
        effort=inter.effort,
        risk=inter.risk,
        score=score,
        rationale=inter.rationale,
        status=inter.status,
        origin=inter.origin,
        created_at=inter.created_at,
        updated_at=inter.updated_at,
    )


@router.patch("/interventions/{intervention_id}")
def update_intervention(
    engagement_id: int,
    intervention_id: int,
    payload: InterventionUpdateRequest,
    db: Session = Depends(get_db),
) -> InterventionResponse:
    """Update an intervention's scoring parameters, status, or description."""
    get_engagement_or_404(db, engagement_id)
    inter = db.get(Intervention, intervention_id)
    if inter is None or inter.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found.")

    if payload.name is not None:
        inter.name = payload.name
    if payload.description is not None:
        inter.description = payload.description
    if payload.impact is not None:
        inter.impact = payload.impact
    if payload.effort is not None:
        inter.effort = payload.effort
    if payload.risk is not None:
        inter.risk = payload.risk
    if payload.rationale is not None:
        inter.rationale = payload.rationale
    if payload.status is not None:
        inter.status = payload.status
    inter.updated_at = datetime.now(timezone.utc)

    score = calculate_intervention_score(inter.impact, inter.effort, inter.risk)
    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="intervention_updated",
        entity_type="intervention",
        entity_id=str(inter.id),
        details={"name": inter.name, "score": score, "status": inter.status},
    )
    db.commit()
    db.refresh(inter)

    return InterventionResponse(
        id=inter.id,
        engagement_id=inter.engagement_id,
        name=inter.name,
        description=inter.description,
        impact=inter.impact,
        effort=inter.effort,
        risk=inter.risk,
        score=score,
        rationale=inter.rationale,
        status=inter.status,
        origin=inter.origin,
        created_at=inter.created_at,
        updated_at=inter.updated_at,
    )


@router.delete("/interventions/{intervention_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intervention(
    engagement_id: int,
    intervention_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete an intervention."""
    get_engagement_or_404(db, engagement_id)
    inter = db.get(Intervention, intervention_id)
    if inter is None or inter.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found.")

    name = inter.name
    db.delete(inter)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="intervention_deleted",
        entity_type="intervention",
        entity_id=str(intervention_id),
        details={"name": name, "intervention_id": intervention_id},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Pilot Simulation Endpoints
# ---------------------------------------------------------------------------


@router.post("/simulations", status_code=status.HTTP_201_CREATED)
@router.post("/simulation", status_code=status.HTTP_201_CREATED)
def create_simulation(
    engagement_id: int,
    payload: SimulationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute synchronous deterministic pilot simulation and store results."""
    get_engagement_or_404(db, engagement_id)
    active_dataset_id = _get_active_dataset_id(db, engagement_id)
    if active_dataset_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Engagement has no active dataset. Upload or select a dataset before running simulations.",
        )

    # Determine rework_share
    eval_run_id: int | None = None
    rework_share = payload.rework_share
    rework_source = "manual"

    if rework_share is None:
        # Retrieve latest completed evaluation run for engagement
        eval_run = db.scalar(
            select(EvalRun)
            .where(EvalRun.engagement_id == engagement_id, EvalRun.status == EvalRunStatus.completed)
            .order_by(EvalRun.id.desc())
            .limit(1)
        )
        if eval_run is None or not eval_run.results:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No completed evaluation run found. Supply a manual rework_share or complete a triage evaluation run first.",
            )
        eval_summary = eval_run.results.get("summary", {})
        rework_share = eval_summary.get("reviewer_change_proxy")
        if rework_share is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Completed evaluation run lacks a reviewer_change_proxy figure. Supply rework_share manually.",
            )
        eval_run_id = eval_run.id
        rework_source = f"eval_run_{eval_run.id}"

    # Build population: tickets included in response and triage scopes with timestamps
    frame, _ = load_ticket_frame(db, active_dataset_id)
    scoped, _ = scope(frame, ("response", "triage"))
    mask = (
        scoped["created_at"].notna()
        & scoped["assigned_at"].notna()
        & scoped["first_response_at"].notna()
    )
    pop = scoped[mask].copy()
    if len(pop) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Active dataset contains no valid tickets satisfying response and triage criteria.",
        )

    # Sort strictly by row_id ascending
    pop = pop.sort_values(by="row_id", ascending=True)

    # Compute hours
    pop["first_response_hours"] = (
        pop["first_response_at"] - pop["created_at"]
    ).dt.total_seconds() / 3600.0
    pop["triage_hours"] = (
        pop["assigned_at"] - pop["created_at"]
    ).dt.total_seconds() / 3600.0

    try:
        sim_results = run_pilot_simulation(
            pop,
            pilot_share=payload.pilot_share,
            reduction_pct=payload.reduction_pct,
            adoption_pct=payload.adoption_pct,
            rework_share=float(rework_share),
            seed=payload.seed,
            rework_share_source=rework_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    sim = PilotSimulation(
        engagement_id=engagement_id,
        dataset_id=active_dataset_id,
        eval_run_id=eval_run_id,
        seed=payload.seed,
        parameters=payload.model_dump(),
        results=sim_results,
        results_hash=sim_results.get("results_hash", ""),
    )
    db.add(sim)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="simulation_created",
        entity_type="pilot_simulation",
        entity_id=str(sim.id),
        details={
            "simulation_id": sim.id,
            "parameters": payload.model_dump(),
            "results_hash": sim.results_hash,
            "dataset_id": active_dataset_id,
        },
    )
    db.commit()
    db.refresh(sim)

    out = dict(sim_results)
    out["id"] = sim.id
    out["eval_run_id"] = sim.eval_run_id
    out["created_at"] = sim.created_at
    return out


@router.get("/simulations")
def list_simulations(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List recent simulations for engagement (newest first, max 10)."""
    get_engagement_or_404(db, engagement_id)
    sims = db.scalars(
        select(PilotSimulation)
        .where(PilotSimulation.engagement_id == engagement_id)
        .order_by(PilotSimulation.id.desc())
        .limit(10)
    ).all()
    results = []
    for s in sims:
        data = dict(s.results)
        data["id"] = s.id
        data["created_at"] = s.created_at
        results.append(data)
    return results


@router.get("/simulations/{simulation_id}")
def get_simulation(
    engagement_id: int,
    simulation_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get single simulation results."""
    get_engagement_or_404(db, engagement_id)
    sim = db.get(PilotSimulation, simulation_id)
    if sim is None or sim.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found.")
    data = dict(sim.results)
    data["id"] = sim.id
    data["created_at"] = sim.created_at
    return data


@router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(
    engagement_id: int,
    simulation_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a simulation run."""
    get_engagement_or_404(db, engagement_id)
    sim = db.get(PilotSimulation, simulation_id)
    if sim is None or sim.engagement_id != engagement_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found.")
    db.delete(sim)
    db.commit()


# ---------------------------------------------------------------------------
# Outcome Review Endpoints
# ---------------------------------------------------------------------------


@router.get("/review")
def get_outcome_review(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current outcome review for engagement."""
    get_engagement_or_404(db, engagement_id)
    rev = db.scalar(
        select(OutcomeReview).where(OutcomeReview.engagement_id == engagement_id)
    )
    if rev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No outcome review found.")
    return {
        "id": rev.id,
        "engagement_id": rev.engagement_id,
        "sections": rev.sections,
        "snapshot": rev.snapshot,
        "source": rev.source,
        "status": rev.status,
        "model": rev.model,
        "usage": rev.usage,
        "flags": rev.flags,
        "final_recommendation": rev.final_recommendation,
        "acknowledged_simulated": rev.acknowledged_simulated,
        "confirmed_at": rev.confirmed_at,
        "updated_at": rev.updated_at,
    }


@router.put("/review")
@router.patch("/review")
def update_outcome_review(
    engagement_id: int,
    payload: OutcomeReviewUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Human edit of outcome review sections. Resets status to draft and revokes confirmation."""
    get_engagement_or_404(db, engagement_id)
    rev = db.scalar(
        select(OutcomeReview).where(OutcomeReview.engagement_id == engagement_id)
    )
    if rev is None:
        # Create empty review to hold edited sections
        snapshot = build_review_snapshot(db, engagement_id)
        rev = OutcomeReview(
            engagement_id=engagement_id,
            sections=payload.sections,
            snapshot=snapshot,
            source="edited",
            status="draft",
            flags=[],
        )
        db.add(rev)
    else:
        # Re-run post-processing on edited sections to update flags
        _, flags = postprocess_outcome_review(payload.sections, rev.snapshot)
        rev.sections = payload.sections
        rev.source = "edited"
        rev.status = "draft"
        rev.confirmed_at = None
        rev.acknowledged_simulated = False
        rev.flags = flags
        rev.updated_at = datetime.now(timezone.utc)

    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="review_edited",
        entity_type="outcome_review",
        entity_id=str(rev.id),
        details={"review_id": rev.id, "source": "edited", "status": "draft"},
    )
    db.commit()
    db.refresh(rev)

    return {
        "id": rev.id,
        "engagement_id": rev.engagement_id,
        "sections": rev.sections,
        "snapshot": rev.snapshot,
        "source": rev.source,
        "status": rev.status,
        "model": rev.model,
        "usage": rev.usage,
        "flags": rev.flags,
        "final_recommendation": rev.final_recommendation,
        "acknowledged_simulated": rev.acknowledged_simulated,
        "confirmed_at": rev.confirmed_at,
        "updated_at": rev.updated_at,
    }


@router.post("/review/draft")
def draft_review(
    engagement_id: int,
    request: Request,
    payload: OutcomeReviewDraftRequest = OutcomeReviewDraftRequest(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Draft an outcome review using configured AI provider."""
    get_engagement_or_404(db, engagement_id)
    settings = _resolve_settings(request)
    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="llm_not_configured",
        )

    # Check KPIs exist
    kpis_count = db.scalar(
        select(Kpi).where(Kpi.engagement_id == engagement_id)
    )
    if not kpis_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot draft outcome review without at least one KPI configured.",
        )

    # Check overwrite guard
    existing_rev = db.scalar(
        select(OutcomeReview).where(OutcomeReview.engagement_id == engagement_id)
    )
    if existing_rev and existing_rev.source == "edited" and not payload.confirm_replace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="would_overwrite_edits",
        )

    # Build snapshot
    objective_text = ""
    if existing_rev and existing_rev.sections:
        objective_text = existing_rev.sections.get("objective", "")
    snapshot = build_review_snapshot(db, engagement_id, objective_text=objective_text)

    provider = _resolve_provider(request, settings)
    try:
        draft_result = draft_outcome_review(provider, snapshot, settings)
    except LLMRateLimited as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMOutputTruncated as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="llm_output_truncated") from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generation failed: {exc}") from exc

    if existing_rev is None:
        existing_rev = OutcomeReview(
            engagement_id=engagement_id,
            sections=draft_result["sections"],
            snapshot=draft_result["snapshot"],
            source="ai_draft",
            status="draft",
            model=draft_result["model"],
            usage=draft_result["usage"],
            flags=draft_result["flags"],
            acknowledged_simulated=False,
            confirmed_at=None,
        )
        db.add(existing_rev)
    else:
        existing_rev.sections = draft_result["sections"]
        existing_rev.snapshot = draft_result["snapshot"]
        existing_rev.source = "ai_draft"
        existing_rev.status = "draft"
        existing_rev.model = draft_result["model"]
        existing_rev.usage = draft_result["usage"]
        existing_rev.flags = draft_result["flags"]
        existing_rev.acknowledged_simulated = False
        existing_rev.confirmed_at = None
        existing_rev.updated_at = datetime.now(timezone.utc)

    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="System",
        action="review_drafted",
        entity_type="outcome_review",
        entity_id=str(existing_rev.id),
        details={"review_id": existing_rev.id, "model": existing_rev.model, "source": "ai_draft"},
    )
    db.commit()
    db.refresh(existing_rev)

    return {
        "id": existing_rev.id,
        "engagement_id": existing_rev.engagement_id,
        "sections": existing_rev.sections,
        "snapshot": existing_rev.snapshot,
        "source": existing_rev.source,
        "status": existing_rev.status,
        "model": existing_rev.model,
        "usage": existing_rev.usage,
        "flags": existing_rev.flags,
        "final_recommendation": existing_rev.final_recommendation,
        "acknowledged_simulated": existing_rev.acknowledged_simulated,
        "confirmed_at": existing_rev.confirmed_at,
        "updated_at": existing_rev.updated_at,
    }


@router.post("/review/confirm")
def confirm_review(
    engagement_id: int,
    payload: OutcomeReviewConfirmRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Human confirmation of outcome review decision."""
    get_engagement_or_404(db, engagement_id)
    if not payload.acknowledged_simulated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirmation requires acknowledging that simulated results are not real-world outcomes.",
        )

    rev = db.scalar(
        select(OutcomeReview).where(OutcomeReview.engagement_id == engagement_id)
    )
    if rev is None or not rev.sections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot confirm an empty outcome review.",
        )

    rev.status = "confirmed"
    rev.final_recommendation = payload.final_recommendation
    rev.acknowledged_simulated = True
    rev.confirmed_at = datetime.now(timezone.utc)
    rev.updated_at = datetime.now(timezone.utc)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        actor="Operator",
        action="review_confirmed",
        entity_type="outcome_review",
        entity_id=str(rev.id),
        details={
            "review_id": rev.id,
            "final_recommendation": rev.final_recommendation,
            "confirmed_at": rev.confirmed_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(rev)

    return {
        "id": rev.id,
        "engagement_id": rev.engagement_id,
        "sections": rev.sections,
        "snapshot": rev.snapshot,
        "source": rev.source,
        "status": rev.status,
        "model": rev.model,
        "usage": rev.usage,
        "flags": rev.flags,
        "final_recommendation": rev.final_recommendation,
        "acknowledged_simulated": rev.acknowledged_simulated,
        "confirmed_at": rev.confirmed_at,
        "updated_at": rev.updated_at,
    }
