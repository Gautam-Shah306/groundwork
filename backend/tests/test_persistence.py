"""Tests for SQLite persistence, engagement/note/brief/activity APIs, and seeding."""

from __future__ import annotations

import re
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.config import Settings
from app.main import create_app
from app.models import AuditLog, Engagement, InterviewNote, ProblemBrief
from app.seed import DEMO_ENGAGEMENT_NAME, DEMO_NOTE_CONTENT, seed_demo_data


@pytest.fixture()
def app_client(tmp_path: Path) -> Generator[tuple[TestClient, object], None, None]:
    db_file = tmp_path / "test_groundwork.db"
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        database_url=f"sqlite:///{db_file.as_posix()}",
        seed_on_start=False,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        yield client, application


def _create_sample_engagement(client: TestClient, name: str = "Kora Support Audit") -> dict:
    response = client.post(
        "/api/engagements",
        json={
            "name": name,
            "client_name": "Kora Living",
            "industry": "D2C home-goods retail",
            "client_statement": "Customers are waiting too long for responses.",
            "stage": "discover",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_engagement_returns_201_and_persists(app_client) -> None:
    client, _ = app_client

    response = client.post(
        "/api/engagements",
        json={
            "name": "Support Triage Discovery",
            "client_name": "Kora Living",
            "industry": "E-commerce",
            "client_statement": "Queue backlog keeps growing.",
            "stage": "discover",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["id"] >= 1
    assert created["name"] == "Support Triage Discovery"
    assert created["client_name"] == "Kora Living"
    assert created["stage"] == "discover"
    assert created["is_synthetic"] is True

    fetched = client.get(f"/api/engagements/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Support Triage Discovery"


def test_create_engagement_rejects_empty_name(app_client) -> None:
    client, _ = app_client

    response = client.post(
        "/api/engagements",
        json={
            "name": "   ",
            "client_name": "Kora Living",
        },
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_engagement_rejects_invalid_stage(app_client) -> None:
    client, _ = app_client

    response = client.post(
        "/api/engagements",
        json={
            "name": "Valid Name",
            "client_name": "Kora Living",
            "stage": "deploy_to_prod",
        },
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_list_engagements_returns_all(app_client) -> None:
    client, _ = app_client
    _create_sample_engagement(client, "Engagement Alpha")
    _create_sample_engagement(client, "Engagement Beta")

    response = client.get("/api/engagements")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert [item["name"] for item in items] == ["Engagement Alpha", "Engagement Beta"]


def test_get_engagement_404_for_unknown_id(app_client) -> None:
    client, _ = app_client

    response = client.get("/api/engagements/99999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_engagement_updates_fields_and_updated_at(app_client) -> None:
    client, _ = app_client
    created = _create_sample_engagement(client)
    original_updated_at = created["updated_at"]

    time.sleep(0.02)
    response = client.patch(
        f"/api/engagements/{created['id']}",
        json={
            "name": "Updated Turnaround Scope",
            "stage": "diagnose",
            "client_statement": "Backlog concentrated in order tracking.",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Turnaround Scope"
    assert updated["stage"] == "diagnose"
    assert updated["client_statement"] == "Backlog concentrated in order tracking."
    assert updated["updated_at"] > original_updated_at


def test_delete_engagement_cascades_to_notes_and_brief(app_client) -> None:
    client, application = app_client
    created = _create_sample_engagement(client)
    eng_id = created["id"]

    note_resp = client.post(
        f"/api/engagements/{eng_id}/notes",
        json={"title": "Intake Call", "content": "Initial stakeholder conversation."},
    )
    assert note_resp.status_code == 201

    brief_resp = client.put(
        f"/api/engagements/{eng_id}/brief",
        json={"sections": {"problem_statement": "Slow triage delays responses."}, "source": "edited"},
    )
    assert brief_resp.status_code == 200

    delete_resp = client.delete(f"/api/engagements/{eng_id}")
    assert delete_resp.status_code == 204

    with application.state.session_factory() as db:
        assert db.get(Engagement, eng_id) is None
        assert db.scalars(select(InterviewNote).where(InterviewNote.engagement_id == eng_id)).all() == []
        assert db.scalars(select(ProblemBrief).where(ProblemBrief.engagement_id == eng_id)).all() == []


def test_create_note_and_list_notes_for_engagement(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)

    create_resp = client.post(
        f"/api/engagements/{eng['id']}/notes",
        json={"title": "Ops Lead Interview", "content": "Team manually drags tickets across folders."},
    )
    assert create_resp.status_code == 201
    note = create_resp.json()
    assert note["engagement_id"] == eng["id"]
    assert note["title"] == "Ops Lead Interview"

    list_resp = client.get(f"/api/engagements/{eng['id']}/notes")
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) == 1
    assert notes[0]["id"] == note["id"]


def test_update_and_delete_note(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)
    note = client.post(
        f"/api/engagements/{eng['id']}/notes",
        json={"title": "Draft Title", "content": "Initial draft content."},
    ).json()

    update_resp = client.put(
        f"/api/engagements/{eng['id']}/notes/{note['id']}",
        json={"title": "Refined Title", "content": "Updated interview notes."},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["title"] == "Refined Title"
    assert updated["content"] == "Updated interview notes."

    delete_resp = client.delete(f"/api/engagements/{eng['id']}/notes/{note['id']}")
    assert delete_resp.status_code == 204

    remaining = client.get(f"/api/engagements/{eng['id']}/notes").json()
    assert remaining == []


def test_note_for_unknown_engagement_returns_404(app_client) -> None:
    client, _ = app_client

    get_resp = client.get("/api/engagements/40404/notes")
    post_resp = client.post(
        "/api/engagements/40404/notes",
        json={"title": "Orphan Note", "content": "Should fail with 404."},
    )

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
    assert "not found" in post_resp.json()["detail"].lower()


def test_brief_get_404_before_first_put(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)

    response = client.get(f"/api/engagements/{eng['id']}/brief")

    assert response.status_code == 404
    assert "no problem brief" in response.json()["detail"].lower()


def test_brief_put_upserts_and_get_returns_it(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)

    first_put = client.put(
        f"/api/engagements/{eng['id']}/brief",
        json={
            "sections": {"problem_statement": "Initial problem statement."},
            "source": "ai_draft",
        },
    )
    assert first_put.status_code == 200
    first_data = first_put.json()
    assert first_data["source"] == "ai_draft"

    second_put = client.put(
        f"/api/engagements/{eng['id']}/brief",
        json={
            "sections": {
                "problem_statement": "Refined testable problem statement.",
                "known_facts": ["Manual triage is used."],
            },
            "source": "edited",
        },
    )
    assert second_put.status_code == 200
    second_data = second_put.json()
    assert second_data["id"] == first_data["id"]
    assert second_data["source"] == "edited"
    assert second_data["sections"]["problem_statement"] == "Refined testable problem statement."

    get_resp = client.get(f"/api/engagements/{eng['id']}/brief")
    assert get_resp.status_code == 200
    assert get_resp.json()["sections"]["known_facts"] == ["Manual triage is used."]


def test_audit_log_written_on_create_update_delete(app_client) -> None:
    client, application = app_client
    eng = _create_sample_engagement(client)
    eng_id = eng["id"]

    client.patch(f"/api/engagements/{eng_id}", json={"stage": "diagnose"})
    note = client.post(
        f"/api/engagements/{eng_id}/notes",
        json={"title": "Call 1", "content": "Notes from call 1."},
    ).json()
    client.put(
        f"/api/engagements/{eng_id}/notes/{note['id']}",
        json={"title": "Call 1 Revised"},
    )
    client.delete(f"/api/engagements/{eng_id}/notes/{note['id']}")
    client.put(
        f"/api/engagements/{eng_id}/brief",
        json={"sections": {"problem_statement": "Draft"}, "source": "edited"},
    )
    client.put(
        f"/api/engagements/{eng_id}/brief",
        json={"sections": {"problem_statement": "Updated"}, "source": "edited"},
    )
    client.delete(f"/api/engagements/{eng_id}")

    with application.state.session_factory() as db:
        entries = db.scalars(
            select(AuditLog)
            .where(AuditLog.engagement_id == eng_id)
            .order_by(AuditLog.id.asc())
        ).all()

    actions = [(e.entity_type, e.action, e.actor) for e in entries]
    assert actions == [
        ("engagement", "create", "Demo operator"),
        ("engagement", "update", "Demo operator"),
        ("note", "create", "Demo operator"),
        ("note", "update", "Demo operator"),
        ("note", "delete", "Demo operator"),
        ("brief", "create", "Demo operator"),
        ("brief", "update", "Demo operator"),
        ("engagement", "delete", "Demo operator"),
    ]


def test_activity_returns_newest_first_and_respects_limit(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)
    eng_id = eng["id"]

    for idx in range(4):
        resp = client.post(
            f"/api/engagements/{eng_id}/notes",
            json={"title": f"Note {idx}", "content": f"Content {idx}"},
        )
        assert resp.status_code == 201

    response = client.get(f"/api/engagements/{eng_id}/activity?limit=3")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3
    ids = [item["id"] for item in items]
    assert ids == sorted(ids, reverse=True)
    assert items[0]["details"]["title"] == "Note 3"


def test_seed_creates_one_engagement_and_note(app_client) -> None:
    client, application = app_client
    with application.state.session_factory() as db:
        result = seed_demo_data(db)

    assert result["created_engagement"] is True
    assert result["created_note"] is True

    engagements = client.get("/api/engagements").json()
    assert len(engagements) == 1
    assert engagements[0]["name"] == DEMO_ENGAGEMENT_NAME
    assert engagements[0]["is_synthetic"] is True
    assert engagements[0]["stage"] == "discover"

    notes = client.get(f"/api/engagements/{engagements[0]['id']}/notes").json()
    assert len(notes) == 1
    word_count = len(notes[0]["content"].split())
    assert 400 <= word_count <= 600


def test_seed_is_idempotent(app_client) -> None:
    client, application = app_client
    with application.state.session_factory() as db:
        first = seed_demo_data(db)
        second = seed_demo_data(db)

    assert first["created_engagement"] is True
    assert second["created_engagement"] is False
    assert second["created_note"] is False
    assert first["engagement_id"] == second["engagement_id"]

    engagements = client.get("/api/engagements").json()
    assert len(engagements) == 1
    notes = client.get(f"/api/engagements/{engagements[0]['id']}/notes").json()
    assert len(notes) == 1


def test_seeded_transcript_contains_no_numeric_metrics_claims() -> None:
    metric_pattern = re.compile(
        r"\d+\s*(%|percent|hours?|hrs?|minutes?|mins?|days?|weeks?|tickets?|agents?)",
        re.IGNORECASE,
    )
    assert metric_pattern.search(DEMO_NOTE_CONTENT) is None
    assert re.search(r"\d", DEMO_NOTE_CONTENT) is None


def test_responses_never_expose_orm_internals(app_client) -> None:
    client, _ = app_client
    eng = _create_sample_engagement(client)
    note = client.post(
        f"/api/engagements/{eng['id']}/notes",
        json={"title": "Check", "content": "Checking response payloads."},
    ).json()
    brief = client.put(
        f"/api/engagements/{eng['id']}/brief",
        json={"sections": {"problem_statement": "Statement"}, "source": "edited"},
    ).json()
    activity = client.get(f"/api/engagements/{eng['id']}/activity").json()

    for payload in (eng, note, brief, *activity):
        assert "_sa_instance_state" not in payload
        assert not any(key.startswith("_") for key in payload.keys())


def test_all_models_create_tables(app_client) -> None:
    _, application = app_client
    inspector = inspect(application.state.engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "engagements",
        "interview_notes",
        "problem_briefs",
        "datasets",
        "tickets",
        "triage_proposals",
        "audit_logs",
        "kpis",
        "eval_runs",
        "pilot_simulations",
    }
    assert expected_tables.issubset(table_names)
