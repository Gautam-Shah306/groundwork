"""FastAPI router for Support Triage prototype endpoints."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.health import resolve_settings
from app.audit import record_audit_event
from app.config import Settings, get_settings
from app.db import get_db
from app.llm import get_provider
from app.llm.errors import (
    LLMError,
    LLMNotConfigured,
    LLMOutputTruncated,
    UnsupportedProvider,
    scrub_secrets,
)
from app.models import AuditLog, Engagement, ProposalStatus, TriageProposal, utc_now
from app.text_utils import compute_ticket_hash
from app.triage.config import TriageConfig, load_triage_config
from app.triage.pipeline import run_triage_pipeline
from app.triage.prompts import ALLOWED_PLACEHOLDERS
from app.triage.schema import (
    CreateProposalRequest,
    ProposalCreateResponse,
    ProposalDecisionRequest,
    ProposalDecisionResponse,
    ProposalFinalValues,
    ProposalsListResponse,
    TriageProposalResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engagements/{engagement_id}/triage", tags=["triage"])

PLACEHOLDER_PATTERN = re.compile(r"\[[A-Za-z0-9_]+\]")


def get_engagement_or_404(db: Session, engagement_id: int) -> Engagement:
    eng = db.get(Engagement, engagement_id)
    if not eng:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found.",
        )
    return eng


def get_proposal_or_404(db: Session, engagement_id: int, proposal_id: int) -> TriageProposal:
    get_engagement_or_404(db, engagement_id)
    proposal = db.get(TriageProposal, proposal_id)
    if not proposal or proposal.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found for engagement {engagement_id}.",
        )
    return proposal


@router.post("/proposals", response_model=ProposalCreateResponse, status_code=status.HTTP_201_CREATED)
def create_proposal_endpoint(
    engagement_id: int,
    payload: CreateProposalRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(resolve_settings),
) -> Any:
    """Submit a ticket to generate an AI triage proposal.

    If a proposal with the same ticket hash exists for this engagement, returns HTTP 200 with duplicate=true
    without calling the AI provider.
    """
    get_engagement_or_404(db, engagement_id)

    # Compute ticket hash
    ticket_hash = compute_ticket_hash(
        subject=payload.subject,
        body=payload.body,
        channel=payload.channel,
    )

    # 1. Idempotency check: return existing proposal if hash matches
    existing = db.scalar(
        select(TriageProposal).where(
            TriageProposal.engagement_id == engagement_id,
            TriageProposal.ticket_hash == ticket_hash,
        )
    )
    if existing:
        response.status_code = status.HTTP_200_OK
        return ProposalCreateResponse(
            proposal=TriageProposalResponse.from_orm_model(existing),
            duplicate=True,
        )

    # 2. Check LLM configuration
    try:
        provider = get_provider(settings)
    except (LLMNotConfigured, UnsupportedProvider) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    # 3. Run pipeline
    triage_config = load_triage_config()
    try:
        proposal, _ = run_triage_pipeline(
            db=db,
            engagement_id=engagement_id,
            subject=payload.subject,
            body=payload.body,
            channel=payload.channel,
            provider=provider,
            config=triage_config,
            max_output_tokens=settings.llm_triage_max_output_tokens,
        )

        # Record audit event (ZERO ticket text, reply text, quotes or secrets)
        record_audit_event(
            db,
            engagement_id=engagement_id,
            action="triage_proposed",
            entity_type="triage_proposal",
            entity_id=proposal.id,
            details={
                "proposal_id": proposal.id,
                "category": proposal.proposed_category,
                "priority": proposal.proposed_priority,
                "queue": proposal.proposed_queue,
                "rule_fired": proposal.rule_fired,
                "model": proposal.model,
                "flag_count": len(proposal.flags or []),
            },
        )
        db.commit()
        db.refresh(proposal)

        return ProposalCreateResponse(
            proposal=TriageProposalResponse.from_orm_model(proposal),
            duplicate=False,
        )

    except IntegrityError:
        # Race condition on unique index (engagement_id, ticket_hash)
        db.rollback()
        race_existing = db.scalar(
            select(TriageProposal).where(
                TriageProposal.engagement_id == engagement_id,
                TriageProposal.ticket_hash == ticket_hash,
            )
        )
        if race_existing:
            return ProposalCreateResponse(
                proposal=TriageProposalResponse.from_orm_model(race_existing),
                duplicate=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_ticket", "message": "A proposal with this ticket hash already exists."},
        )

    except LLMOutputTruncated as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    except LLMError as exc:
        db.rollback()
        msg = scrub_secrets(str(exc), secrets=(settings.llm_api_key,))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": msg},
        ) from exc

    except Exception as exc:
        db.rollback()
        msg = scrub_secrets(str(exc), secrets=(settings.llm_api_key,))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "triage_pipeline_error", "message": msg},
        ) from exc


@router.get("/proposals", response_model=ProposalsListResponse)
def list_proposals_endpoint(
    engagement_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> ProposalsListResponse:
    """List triage proposals for the engagement, newest first, with optional status filter."""
    get_engagement_or_404(db, engagement_id)

    query = select(TriageProposal).where(TriageProposal.engagement_id == engagement_id)
    if status_filter:
        query = query.where(TriageProposal.status == status_filter)

    # Count total
    all_matching = db.scalars(query).all()
    total = len(all_matching)

    offset = (page - 1) * page_size
    proposals = (
        db.scalars(
            query.order_by(TriageProposal.created_at.desc(), TriageProposal.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        .all()
    )

    return ProposalsListResponse(
        items=[TriageProposalResponse.from_orm_model(p) for p in proposals],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/proposals/{proposal_id}", response_model=TriageProposalResponse)
def get_proposal_endpoint(
    engagement_id: int,
    proposal_id: int,
    db: Session = Depends(get_db),
) -> TriageProposalResponse:
    """Get a single triage proposal by ID."""
    proposal = get_proposal_or_404(db, engagement_id, proposal_id)
    return TriageProposalResponse.from_orm_model(proposal)


@router.get("/proposals/{proposal_id}/history", response_model=list[dict[str, Any]])
def get_proposal_history_endpoint(
    engagement_id: int,
    proposal_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return immutable audit log events for this proposal, oldest first."""
    get_proposal_or_404(db, engagement_id, proposal_id)

    events = (
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.engagement_id == engagement_id,
                AuditLog.entity_type == "triage_proposal",
                AuditLog.entity_id == str(proposal_id),
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
        .all()
    )

    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "created_at": e.created_at,
            "details": e.details,
        }
        for e in events
    ]


@router.post("/proposals/{proposal_id}/decision", response_model=ProposalDecisionResponse)
def record_decision_endpoint(
    engagement_id: int,
    proposal_id: int,
    payload: ProposalDecisionRequest,
    db: Session = Depends(get_db),
) -> ProposalDecisionResponse:
    """Record human approval or rejection of a proposal (R3).

    Atomic and conditional on status='awaiting_approval'. Zero rows updated returns HTTP 409 already_decided.
    Nothing is ever sent to customers.
    """
    proposal = get_proposal_or_404(db, engagement_id, proposal_id)

    config = load_triage_config()
    known_categories = {c.id for c in config.categories}
    known_queues = set(config.queues)

    # Validation
    final_dict: dict[str, Any] = {}
    edited_fields: list[str] = []
    unresolved_placeholders: list[str] = []

    if payload.decision == "approve":
        # Resolve final values
        cat = (payload.final.category if payload.final and payload.final.category else proposal.proposed_category).strip()
        pri = (payload.final.priority if payload.final and payload.final.priority else proposal.proposed_priority).strip().lower()
        que = (payload.final.queue if payload.final and payload.final.queue else proposal.proposed_queue).strip()
        rep = (payload.final.reply_text if payload.final and payload.final.reply_text is not None else proposal.draft_reply).strip()

        if not rep:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "empty_reply", "message": "Approval requires a non-empty customer reply."},
            )
        if len(rep) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "reply_too_long", "message": "Reply exceeds 2000 character maximum."},
            )
        if cat not in known_categories:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "invalid_category", "message": f"Category '{cat}' is not in configured vocabulary."},
            )
        if pri not in ("low", "medium", "high"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "invalid_priority", "message": f"Priority '{pri}' must be low, medium, or high."},
            )
        if que not in known_queues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "invalid_queue", "message": f"Queue '{que}' is not in configured queues."},
            )

        if cat != proposal.proposed_category:
            edited_fields.append("category")
        if pri != proposal.proposed_priority:
            edited_fields.append("priority")
        if que != proposal.proposed_queue:
            edited_fields.append("queue")
        if rep != proposal.draft_reply:
            edited_fields.append("reply_text")

        final_dict = {
            "category": cat,
            "priority": pri,
            "queue": que,
            "reply_text": rep,
            "edited_fields": edited_fields,
        }

        # Check for unresolved placeholders in approved reply
        matches = PLACEHOLDER_PATTERN.findall(rep)
        unresolved_placeholders = [ph for ph in matches if ph in ALLOWED_PLACEHOLDERS]

    decided_at = utc_now()
    new_status = ProposalStatus.approved if payload.decision == "approve" else ProposalStatus.rejected
    is_edited = len(edited_fields) > 0
    actor_name = "Demo operator"

    # Atomic conditional update
    stmt = (
        update(TriageProposal)
        .where(
            TriageProposal.id == proposal_id,
            TriageProposal.engagement_id == engagement_id,
            TriageProposal.status == ProposalStatus.awaiting_approval,
        )
        .values(
            status=new_status,
            final_values=final_dict if payload.decision == "approve" else None,
            edited=is_edited,
            decided_by=actor_name,
            decided_at=decided_at,
            decision_reason=payload.reason,
        )
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "already_decided",
                "message": "This proposal has already been decided and cannot be modified.",
            },
        )

    # Record triage_decision audit event
    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="triage_decision",
        entity_type="triage_proposal",
        entity_id=proposal_id,
        actor=actor_name,
        details={
            "decision": payload.decision,
            "edited": is_edited,
            "edited_fields": edited_fields,
            "original_category": proposal.proposed_category,
            "final_category": final_dict.get("category", proposal.proposed_category),
            "original_priority": proposal.proposed_priority,
            "final_priority": final_dict.get("priority", proposal.proposed_priority),
            "original_queue": proposal.proposed_queue,
            "final_queue": final_dict.get("queue", proposal.proposed_queue),
            "priority_overrides_rule": final_dict.get("priority") != proposal.proposed_priority if payload.decision == "approve" else False,
            "reply_changed": "reply_text" in edited_fields,
            "reply_length": len(final_dict.get("reply_text", "")),
            "unresolved_placeholders_count": len(unresolved_placeholders),
            "reason": payload.reason,
        },
    )
    db.commit()

    return ProposalDecisionResponse(
        proposal_id=proposal_id,
        decision=payload.decision,
        status=new_status.value if hasattr(new_status, "value") else str(new_status),
        edited=is_edited,
        edited_fields=edited_fields,
        unresolved_placeholders=unresolved_placeholders,
        decided_by=actor_name,
        decided_at=decided_at,
    )
