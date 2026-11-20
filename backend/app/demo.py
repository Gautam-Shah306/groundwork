"""Demo preparation CLI for Groundwork (A4).

Prepares or resets the Kora Living engagement (id=1) for live demonstrations.
Usage:
    python -m app.demo prepare [--reset-outcomes] [--clear-proposals] [--yes]
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import create_db_engine, create_session_factory, init_db
from app.models import (
    AuditLog,
    Dataset,
    Engagement,
    EvalRun,
    EvalRunStatus,
    Intervention,
    Kpi,
    OutcomeReview,
    PilotSimulation,
    TriageProposal,
)
from app.outcomes.service import seed_interventions_if_needed


def prepare_demo(
    db: Session,
    reset_outcomes: bool = False,
    clear_proposals: bool = False,
    auto_confirm: bool = False,
) -> dict[str, int | str | bool]:
    """Prepare engagement 1 for demonstration, idempotently ensuring data state."""
    actions: dict[str, int | str | bool] = {
        "engagement_created": False,
        "proposals_cleared": 0,
        "audit_logs_cleared": 0,
        "simulations_cleared": 0,
        "reviews_reset": 0,
        "interventions_restored": 0,
    }

    # 1. Ensure Engagement 1 exists
    eng = db.get(Engagement, 1)
    if eng is None:
        eng = Engagement(
            id=1,
            name="Kora Living",
            client_name="Kora Living",
            stage="build",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        actions["engagement_created"] = True

    # Ensure interventions seeded
    interventions = seed_interventions_if_needed(db, eng.id)

    # 2. Clear proposals if requested
    if clear_proposals:
        deleted_props = db.execute(
            delete(TriageProposal).where(TriageProposal.engagement_id == eng.id)
        ).rowcount
        deleted_audits = db.execute(
            delete(AuditLog).where(
                AuditLog.engagement_id == eng.id,
                AuditLog.action.in_(["proposal_created", "proposal_approved", "proposal_edited", "proposal_rejected"]),
            )
        ).rowcount
        db.commit()
        actions["proposals_cleared"] = deleted_props
        actions["audit_logs_cleared"] = deleted_audits

    # 3. Reset outcomes if requested
    if reset_outcomes:
        # Clear pilot simulations
        del_sims = db.execute(
            delete(PilotSimulation).where(PilotSimulation.engagement_id == eng.id)
        ).rowcount
        actions["simulations_cleared"] = del_sims

        # Reset outcome reviews
        rev = db.scalar(
            select(OutcomeReview).where(OutcomeReview.engagement_id == eng.id)
        )
        if rev is not None:
            db.delete(rev)
            actions["reviews_reset"] = 1

        # Reset custom interventions: delete non-seeded, restore seeded defaults
        db.execute(
            delete(Intervention).where(
                Intervention.engagement_id == eng.id,
                Intervention.origin != "seeded",
            )
        )
        # Restore seeded catalogue interventions to proposed status
        catalogue_items = db.scalars(
            select(Intervention).where(
                Intervention.engagement_id == eng.id,
                Intervention.origin == "seeded",
            )
        ).all()
        for ci in catalogue_items:
            ci.status = "proposed"
        actions["interventions_restored"] = len(catalogue_items)
        db.commit()

    return actions


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.demo",
        description="Groundwork Demo Environment Preparation CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep_parser = subparsers.add_parser("prepare", help="Prepare engagement 1 for demonstration")
    prep_parser.add_argument(
        "--reset-outcomes",
        action="store_true",
        help="Reset confirmed review, simulations, and restore default interventions",
    )
    prep_parser.add_argument(
        "--clear-proposals",
        action="store_true",
        help="Clear triage proposals and audit events for engagement 1",
    )
    prep_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Bypass interactive confirmation prompt",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        if not args.yes and (args.reset_outcomes or args.clear_proposals):
            confirm = input("This will modify demo data for Engagement 1. Proceed? [y/N]: ")
            if confirm.strip().lower() not in ("y", "yes"):
                print("Aborted.")
                return 1

        settings = get_settings()
        engine = create_db_engine(settings.resolved_database_url)
        init_db(engine)
        session_factory = create_session_factory(engine)

        with session_factory() as session:
            results = prepare_demo(
                session,
                reset_outcomes=args.reset_outcomes,
                clear_proposals=args.clear_proposals,
                auto_confirm=args.yes,
            )

        print("=== Groundwork Demo Preparation Complete ===")
        print(f"Engagement 1 created:     {results['engagement_created']}")
        print(f"Proposals cleared:        {results['proposals_cleared']}")
        print(f"Audit logs cleared:       {results['audit_logs_cleared']}")
        print(f"Simulations cleared:      {results['simulations_cleared']}")
        print(f"Reviews reset:            {results['reviews_reset']}")
        print(f"Interventions restored:   {results['interventions_restored']}")
        print("Ready for live demonstration.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
