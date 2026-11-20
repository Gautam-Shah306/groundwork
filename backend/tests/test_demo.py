"""Unit tests for the Demo preparation CLI (A4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import create_db_engine, create_session_factory, init_db
from app.demo import build_parser, main, prepare_demo
from app.models import (
    AuditLog,
    Engagement,
    Intervention,
    OutcomeReview,
    PilotSimulation,
    ProposalStatus,
    TriageProposal,
)


@pytest.fixture()
def demo_db(tmp_path: Path):
    db_file = tmp_path / "test_demo.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_db_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    return engine, session_factory


def test_prepare_creates_engagement_1_if_missing(demo_db):
    """Test 1: prepare creates engagement 1 with Kora Living name if missing."""
    _, session_factory = demo_db
    with session_factory() as session:
        assert session.get(Engagement, 1) is None
        actions = prepare_demo(session)
        assert actions["engagement_created"] is True
        eng = session.get(Engagement, 1)
        assert eng is not None
        assert eng.name == "Kora Living"
        assert eng.client_name == "Kora Living"


def test_prepare_is_idempotent_on_existing_engagement(demo_db):
    """Test 2: prepare is idempotent and does not recreate existing engagement."""
    _, session_factory = demo_db
    with session_factory() as session:
        prepare_demo(session)
        actions2 = prepare_demo(session)
        assert actions2["engagement_created"] is False
        assert session.get(Engagement, 1) is not None


def test_prepare_clear_proposals_deletes_proposals_and_audits(demo_db):
    """Test 3: prepare --clear-proposals deletes triage proposals and related audit entries."""
    _, session_factory = demo_db
    with session_factory() as session:
        prepare_demo(session)
        prop = TriageProposal(
            engagement_id=1,
            ticket_text="Test body",
            proposed_category="order_tracking",
            proposed_priority="medium",
            proposed_queue="Order support",
            reasoning="Test reasoning",
            draft_reply="Test reply",
            status=ProposalStatus.awaiting_approval,
        )
        audit = AuditLog(
            engagement_id=1,
            actor="System",
            action="proposal_created",
            entity_type="triage_proposal",
            entity_id="1",
        )
        session.add_all([prop, audit])
        session.commit()

        actions = prepare_demo(session, clear_proposals=True)
        assert actions["proposals_cleared"] >= 1
        assert actions["audit_logs_cleared"] >= 1

        remaining_props = session.scalars(select(TriageProposal).where(TriageProposal.engagement_id == 1)).all()
        assert len(remaining_props) == 0


def test_prepare_reset_outcomes_resets_reviews_simulations_interventions(demo_db):
    """Test 4: prepare --reset-outcomes clears simulations, reviews, and restores default interventions."""
    _, session_factory = demo_db
    with session_factory() as session:
        prepare_demo(session)
        # Add a simulation
        sim = PilotSimulation(engagement_id=1, parameters={}, results={})
        # Add an outcome review
        rev = OutcomeReview(
            engagement_id=1,
            status="confirmed",
            sections={"recommendation": {"value": "continue"}},
            final_recommendation="continue",
        )
        # Add a custom intervention
        custom_inter = Intervention(
            engagement_id=1,
            name="Custom Workflow",
            impact=4,
            effort=2,
            risk=2,
            origin="human",
        )
        session.add_all([sim, rev, custom_inter])
        session.commit()

        actions = prepare_demo(session, reset_outcomes=True)
        assert actions["simulations_cleared"] >= 1
        assert actions["reviews_reset"] == 1
        assert actions["interventions_restored"] >= 4

        # Confirm custom deleted and review deleted
        remaining_sims = session.scalars(select(PilotSimulation).where(PilotSimulation.engagement_id == 1)).all()
        assert len(remaining_sims) == 0
        remaining_rev = session.scalars(select(OutcomeReview).where(OutcomeReview.engagement_id == 1)).all()
        assert len(remaining_rev) == 0
        customs = session.scalars(select(Intervention).where(Intervention.origin == "human")).all()
        assert len(customs) == 0


def test_prepare_yes_flag_bypasses_interactive_prompt(monkeypatch, tmp_path):
    """Test 5: prepare --yes executes without prompting for stdin input."""
    db_file = tmp_path / "test_yes.db"
    test_settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
    )
    with patch("app.demo.get_settings", return_value=test_settings):
        # Without mocking input, this should NOT call input() and exit 0
        code = main(["prepare", "--clear-proposals", "--reset-outcomes", "--yes"])
        assert code == 0


def test_prepare_cli_prints_summary(capsys, monkeypatch, tmp_path):
    """Test 6: prepare CLI prints summary of actions taken."""
    db_file = tmp_path / "test_summary.db"
    test_settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
    )
    with patch("app.demo.get_settings", return_value=test_settings):
        code = main(["prepare", "--yes"])
        assert code == 0
        captured = capsys.readouterr().out
        assert "=== Groundwork Demo Preparation Complete ===" in captured
        assert "Engagement 1 created:" in captured
        assert "Ready for live demonstration." in captured


def test_prepare_parser_invalid_argument_and_help(capsys):
    """Test 7: CLI parser raises SystemExit on invalid argument or --help."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--unknown-flag"])

    with pytest.raises(SystemExit):
        parser.parse_args(["prepare", "--invalid"])
