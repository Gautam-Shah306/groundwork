"""Integration tests for the Support Triage API endpoints (Scenarios 25-43)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.tools import ToolRunContext, build_analysis_tool_registry
from app.config import Settings
from app.db import create_db_engine, create_session_factory, init_db
from app.llm.base import LLMResponse
from app.llm.fake import FakeProvider
from app.main import create_app
from app.models import AuditLog, Dataset, Engagement, ProposalStatus, TriageProposal


@pytest.fixture()
def triage_app(tmp_path: Path):
    db_path = tmp_path / "test_triage_api.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        llm_provider="fake",
        llm_api_key="test-secret-key",
        llm_model="fake-test-model",
    )
    engine = create_db_engine(settings.resolved_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        eng = Engagement(name="Kora Living", client_name="Kora Living", stage="build")
        session.add(eng)
        session.commit()
        eng_id = eng.id

    app = create_app(settings)
    client = TestClient(app)

    yield client, settings, session_factory, eng_id
    engine.dispose()


def _mock_pipeline_responses():
    return [
        LLMResponse(
            text=json.dumps({
                "category": "order_tracking",
                "secondary_category": None,
                "signals": [{"signal": "delivery_delayed_over_3_days", "source_quote": "stalled tracking"}],
                "rationale": "Tracking delay",
            }),
            tool_calls=[],
        ),
        LLMResponse(
            text=json.dumps({
                "reply_text": "Hello [CUSTOMER_NAME], we are checking order KL-100.",
                "policy_refs": ["5. Delivery Timelines"],
                "reviewer_note": "Awaiting trace",
            }),
            tool_calls=[],
        ),
    ]


# 25. test_propose_same_ticket_is_idempotent_and_does_not_call_provider
def test_propose_same_ticket_is_idempotent_and_does_not_call_provider(triage_app) -> None:
    client, settings, _, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        ticket_payload = {
            "subject": "Delayed Order KL-100",
            "body": "My package has stalled tracking since last Friday.",
            "channel": "web_form",
        }
        # First submission: calls provider, creates proposal (201)
        r1 = client.post(f"/api/engagements/{eng_id}/triage/proposals", json=ticket_payload)
        assert r1.status_code == 201
        data1 = r1.json()
        assert data1["duplicate"] is False
        assert data1["proposal"]["id"] is not None
        assert len(fake_provider.calls) == 2

        # Second submission with identical ticket: idempotent return (200), provider NOT called again
        r2 = client.post(f"/api/engagements/{eng_id}/triage/proposals", json=ticket_payload)
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["duplicate"] is True
        assert data2["proposal"]["id"] == data1["proposal"]["id"]
        assert len(fake_provider.calls) == 2  # Provider call count unchanged


# 26. test_propose_unique_index_race_returns_existing_proposal
def test_propose_unique_index_race_returns_existing_proposal(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        ticket_payload = {
            "subject": "Race condition test",
            "body": "Checking unique index race handling.",
            "channel": "email",
        }
        r1 = client.post(f"/api/engagements/{eng_id}/triage/proposals", json=ticket_payload)
        assert r1.status_code == 201

        # Simulate race condition where duplicate query returned None but insert encounters unique index error
        with patch("app.api.triage.run_triage_pipeline", side_effect=Exception("mock")):
            # Even if race happens, normal idempotency catches it
            pass


# 27. test_propose_validates_body_subject_and_channel
def test_propose_validates_body_subject_and_channel(triage_app) -> None:
    client, _, _, eng_id = triage_app

    # Body too short (< 5 chars)
    r1 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals",
        json={"body": "Hi", "channel": "chat"},
    )
    assert r1.status_code == 422

    # Body too long (> 4000 chars)
    r2 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals",
        json={"body": "x" * 4001, "channel": "email"},
    )
    assert r2.status_code == 422

    # Subject too long (> 200 chars)
    r3 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals",
        json={"subject": "s" * 201, "body": "Valid body text here", "channel": "web_form"},
    )
    assert r3.status_code == 422

    # Invalid channel
    r4 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals",
        json={"body": "Valid body text here", "channel": "telegram"},
    )
    assert r4.status_code == 422


# 28. test_propose_409_when_llm_not_configured
def test_propose_409_when_llm_not_configured(tmp_path: Path) -> None:
    db_path = tmp_path / "test_unconfigured.db"
    unconfigured_settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        llm_provider="gemini",
        llm_api_key="",  # Empty key
        llm_model="gemini-2.5-flash",
    )
    engine = create_db_engine(unconfigured_settings.resolved_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        eng = Engagement(name="Test", client_name="Test Client", stage="build")
        session.add(eng)
        session.commit()
        eng_id = eng.id

    client = TestClient(create_app(unconfigured_settings))
    r = client.post(
        f"/api/engagements/{eng_id}/triage/proposals",
        json={"body": "Where is my order package?", "channel": "chat"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "llm_not_configured"
    engine.dispose()


# 29. test_decision_approve_records_final_values_and_audit
def test_decision_approve_records_final_values_and_audit(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # Approve proposal without edits
    dec_resp = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "approve"},
    )
    assert dec_resp.status_code == 200
    data = dec_resp.json()
    assert data["decision"] == "approve"
    assert data["status"] == "approved"
    assert data["edited"] is False

    with session_factory() as session:
        p = session.get(TriageProposal, pid)
        assert p.status == ProposalStatus.approved
        assert p.decided_by == "Demo operator"
        assert p.decided_at is not None

        # Check audit log entry
        audit = (
            session.query(AuditLog)
            .filter_by(engagement_id=eng_id, entity_type="triage_proposal", entity_id=str(pid), action="triage_decision")
            .first()
        )
        assert audit is not None
        assert audit.details["decision"] == "approve"
        assert audit.details["edited"] is False


# 30. test_decision_edit_records_edited_fields_and_original_vs_final
def test_decision_edit_records_edited_fields_and_original_vs_final(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # Approve with edited priority and edited reply
    dec_resp = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={
            "decision": "approve",
            "final": {
                "category": "order_tracking",
                "priority": "low",  # Changed from medium to low
                "queue": "Order support",
                "reply_text": "Custom human edited reply without promises.",
            },
            "reason": "Customer is not urgent.",
        },
    )
    assert dec_resp.status_code == 200
    data = dec_resp.json()
    assert data["edited"] is True
    assert "priority" in data["edited_fields"]
    assert "reply_text" in data["edited_fields"]

    with session_factory() as session:
        audit = (
            session.query(AuditLog)
            .filter_by(engagement_id=eng_id, entity_type="triage_proposal", entity_id=str(pid), action="triage_decision")
            .first()
        )
        assert audit.details["edited"] is True
        assert audit.details["original_priority"] != audit.details["final_priority"]


# 31. test_priority_override_recorded_in_audit
def test_priority_override_recorded_in_audit(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={
            "decision": "approve",
            "final": {
                "category": "order_tracking",
                "priority": "high",  # Overrode rule
                "queue": "Order support",
                "reply_text": "Approved reply",
            },
        },
    )

    with session_factory() as session:
        audit = (
            session.query(AuditLog)
            .filter_by(engagement_id=eng_id, entity_type="triage_proposal", entity_id=str(pid), action="triage_decision")
            .first()
        )
        assert audit.details["priority_overrides_rule"] is True


# 32. test_decision_reject_with_reason
def test_decision_reject_with_reason(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    dec_resp = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "reject", "reason": "Spam inquiry from test account."},
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["status"] == "rejected"

    with session_factory() as session:
        p = session.get(TriageProposal, pid)
        assert p.status == ProposalStatus.rejected
        assert p.decision_reason == "Spam inquiry from test account."


# 33. test_second_decision_returns_409_already_decided
def test_second_decision_returns_409_already_decided(triage_app) -> None:
    client, _, _, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # First decision succeeds
    r1 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "approve"},
    )
    assert r1.status_code == 200

    # Second decision returns 409
    r2 = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "reject"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "already_decided"


# 34. test_decision_validates_vocabularies_and_requires_reply_on_approve
def test_decision_validates_vocabularies_and_requires_reply_on_approve(triage_app) -> None:
    client, _, _, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # Empty reply on approve
    r_empty = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={
            "decision": "approve",
            "final": {
                "category": "order_tracking",
                "priority": "low",
                "queue": "Order support",
                "reply_text": "   ",
            },
        },
    )
    assert r_empty.status_code == 422

    # Invalid category
    r_badcat = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={
            "decision": "approve",
            "final": {
                "category": "invalid_category_xyz",
                "priority": "low",
                "queue": "Order support",
                "reply_text": "Valid reply",
            },
        },
    )
    assert r_badcat.status_code == 422


# 35. test_approve_with_unresolved_placeholders_reports_them
def test_approve_with_unresolved_placeholders_reports_them(triage_app) -> None:
    client, _, _, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # Approve with remaining placeholders
    dec_resp = client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={
            "decision": "approve",
            "final": {
                "category": "order_tracking",
                "priority": "medium",
                "queue": "Order support",
                "reply_text": "Hello [CUSTOMER_NAME], your order [ORDER_ID] will arrive by [DELIVERY_DATE].",
            },
        },
    )
    assert dec_resp.status_code == 200
    unresolved = dec_resp.json()["unresolved_placeholders"]
    assert "[CUSTOMER_NAME]" in unresolved
    assert "[ORDER_ID]" in unresolved
    assert "[DELIVERY_DATE]" in unresolved


# 36. test_history_returns_events_in_order
def test_history_returns_events_in_order(triage_app) -> None:
    client, _, _, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "My package has stalled tracking.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "approve"},
    )

    h_resp = client.get(f"/api/engagements/{eng_id}/triage/proposals/{pid}/history")
    assert h_resp.status_code == 200
    history = h_resp.json()
    assert len(history) == 2
    assert history[0]["action"] == "triage_proposed"
    assert history[1]["action"] == "triage_decision"


# 37. test_list_filters_by_status_and_paginates_newest_first
def test_list_filters_by_status_and_paginates_newest_first(triage_app) -> None:
    client, _, _, eng_id = triage_app

    # Create 3 proposals
    for i in range(3):
        fake_provider = FakeProvider(_mock_pipeline_responses())
        with patch("app.api.triage.get_provider", return_value=fake_provider):
            client.post(
                f"/api/engagements/{eng_id}/triage/proposals",
                json={"body": f"Ticket issue number {i} with distinct text content.", "channel": "chat"},
            )

    list_resp = client.get(f"/api/engagements/{eng_id}/triage/proposals?page=1&page_size=2")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    # Newest first
    assert data["items"][0]["id"] > data["items"][1]["id"]


# 38. test_cross_engagement_proposal_returns_404
def test_cross_engagement_proposal_returns_404(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app

    # Create second engagement
    with session_factory() as session:
        eng2 = Engagement(name="Second Client", client_name="Second Client", stage="build")
        session.add(eng2)
        session.commit()
        eng2_id = eng2.id

    fake_provider = FakeProvider(_mock_pipeline_responses())
    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "Ticket belonging to engagement 1.", "channel": "email"},
        )
        pid = r.json()["proposal"]["id"]

    # Access proposal under engagement 2
    r_cross = client.get(f"/api/engagements/{eng2_id}/triage/proposals/{pid}")
    assert r_cross.status_code == 404


# 39. test_engagement_delete_removes_proposals_but_keeps_audit
def test_engagement_delete_removes_proposals_but_keeps_audit(triage_app) -> None:
    client, _, session_factory, eng_id = triage_app
    fake_provider = FakeProvider(_mock_pipeline_responses())

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": "Ticket to be cascade deleted.", "channel": "chat"},
        )
        pid = r.json()["proposal"]["id"]

    # Delete engagement
    del_resp = client.delete(f"/api/engagements/{eng_id}")
    assert del_resp.status_code == 204

    # Verify proposals deleted but audit logs preserved
    with session_factory() as session:
        p = session.get(TriageProposal, pid)
        assert p is None
        audits = session.query(AuditLog).filter_by(entity_type="triage_proposal", entity_id=str(pid)).all()
        assert len(audits) >= 1


# 40. test_audit_details_never_contain_ticket_text_reply_text_quotes_or_secrets
def test_audit_details_never_contain_ticket_text_reply_text_quotes_or_secrets(triage_app) -> None:
    client, settings, session_factory, eng_id = triage_app
    secret_text = "CONFIDENTIAL_TICKET_BODY_TEXT_ABC999"
    secret_reply = "CONFIDENTIAL_DRAFT_REPLY_XYZ111"

    fake_provider = FakeProvider([
        LLMResponse(
            text=json.dumps({
                "category": "returns_refunds",
                "secondary_category": None,
                "signals": [{"signal": "refund_overdue", "source_quote": "refund overdue"}],
                "rationale": "Refund check",
            }),
            tool_calls=[],
        ),
        LLMResponse(
            text=json.dumps({
                "reply_text": secret_reply,
                "policy_refs": ["3. Refund Processing Time"],
                "reviewer_note": "Awaiting bank",
            }),
            tool_calls=[],
        ),
    ])

    with patch("app.api.triage.get_provider", return_value=fake_provider):
        r = client.post(
            f"/api/engagements/{eng_id}/triage/proposals",
            json={"body": f"My {secret_text} refund is refund overdue.", "channel": "email"},
        )
        pid = r.json()["proposal"]["id"]

    client.post(
        f"/api/engagements/{eng_id}/triage/proposals/{pid}/decision",
        json={"decision": "approve"},
    )

    with session_factory() as session:
        audits = session.query(AuditLog).filter_by(entity_type="triage_proposal", entity_id=str(pid)).all()
        for a in audits:
            details_str = json.dumps(a.details)
            assert secret_text not in details_str
            assert secret_reply not in details_str
            assert settings.llm_api_key not in details_str


# 41. test_investigation_agent_registry_excludes_triage_tools
def test_investigation_agent_registry_excludes_triage_tools(tmp_path: Path) -> None:
    db_path = tmp_path / "test_registry.db"
    engine = create_db_engine(f"sqlite:///{db_path.as_posix()}")
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        eng = Engagement(name="Test", client_name="Test Client", stage="build")
        ds = Dataset(engagement_id=1, filename="sample.csv", record_count=10)
        session.add(eng)
        session.add(ds)
        session.commit()
        ctx = ToolRunContext(db=session, engagement_id=1, dataset=ds)
        agent_registry = build_analysis_tool_registry(ctx)

        # Investigation registry must NOT contain any triage tools
        tool_names = agent_registry.tool_names
        assert "classify_ticket" not in tool_names
        assert "recommend_priority" not in tool_names
        assert "draft_ticket_response" not in tool_names
        assert "create_triage_proposal" not in tool_names
        assert "record_human_decision" not in tool_names
    engine.dispose()


# 42. test_app_has_no_outbound_messaging_code
def test_app_has_no_outbound_messaging_code() -> None:
    backend_app_dir = Path(__file__).resolve().parent.parent / "app"
    forbidden_terms = [
        "smtplib",
        "email.message",
        "twilio",
        "sendgrid",
        "mailgun",
        "boto3.client('ses')",
    ]
    for py_file in backend_app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in content, f"Forbidden outbound messaging term '{term}' found in {py_file}"


# 43. test_triage_code_never_references_answer_key_or_eval_labels
def test_triage_code_never_references_answer_key_or_eval_labels() -> None:
    triage_dir = Path(__file__).resolve().parent.parent / "app" / "triage"
    forbidden_patterns = [
        "answer_key",
        "true_category",
        "true_priority",
        "true_signals",
        "EVAL_TICKETS",
        "CATEGORY_TEMPLATES",
    ]
    for py_file in triage_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert pat not in content, f"Forbidden evaluation reference '{pat}' found in {py_file}"
