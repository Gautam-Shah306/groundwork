"""Integration tests for the Assistant runs API and persistence (Part E, scenarios 1-12)."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from app.api.assistant import get_provider_factory
from app.config import Settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolSchema
from app.llm.errors import LLMProviderError
from app.llm.fake import FakeProvider
from app.main import create_app
from app.models import AgentRun, AgentRunStatus, AnswerStatus, AuditLog


def _make_app(
    tmp_path,
    *,
    db_name: str = "assistant_api.db",
    llm_api_key: str = "synthetic-test-key-xyz999",
    llm_model: str = "fake-gemini-model",
    provider: LLMProvider | None = None,
):
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        database_url=f"sqlite:///{tmp_path.as_posix()}/{db_name}",
        seed_on_start=True,
    )
    app = create_app(settings)
    if provider is not None:
        app.dependency_overrides[get_provider_factory] = lambda: (lambda _s: provider)
    return app, settings


def _load_sample(client: TestClient, engagement_id: int = 1) -> int:
    resp = client.post(f"/api/engagements/{engagement_id}/datasets/sample")
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _poll_until_done(
    client: TestClient,
    engagement_id: int,
    run_id: int,
    timeout: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/engagements/{engagement_id}/assistant/runs/{run_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(0.03)
    raise AssertionError(f"Run {run_id} did not finish in time; last={last}")


def test_post_run_returns_202_and_run_completes(tmp_path) -> None:
    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="get_response_metrics",
                        arguments={"metric": "first_response_time"},
                    )
                ]
            ),
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "finding",
                                "text": "Median first-response time is 6.07 hours.",
                                "evidence_call_ids": ["c1"],
                            }
                        ]
                    }
                )
            ),
        ],
        model_name="fake-gemini-2.5",
    )
    app, _ = _make_app(tmp_path, db_name="t1.db", provider=provider)
    with TestClient(app) as client:
        ds_id = _load_sample(client)
        post = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Why are customers waiting so long?"},
        )
        assert post.status_code == 202
        body = post.json()
        assert body["status"] == "running"
        assert isinstance(body["run_id"], int)

        final = _poll_until_done(client, 1, body["run_id"])
        assert final["status"] == "completed"
        assert final["answer_status"] == "structured"
        assert final["dataset_id"] == ds_id
        assert len(final["tool_trace"]) == 1
        assert final["answer_blocks"][0]["type"] == "finding"
        assert final["warnings"] == []


def test_post_run_409_when_llm_not_configured(tmp_path) -> None:
    app, _ = _make_app(
        tmp_path,
        db_name="t2.db",
        llm_api_key="",
        llm_model="",
        provider=None,
    )
    with TestClient(app) as client:
        _load_sample(client)
        post = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Why are customers waiting?"},
        )
        assert post.status_code == 409
        detail = post.json()["detail"]
        assert detail["code"] == "llm_not_configured"
        assert "LLM_API_KEY" in detail["message"]


def test_post_run_validates_question_length(tmp_path) -> None:
    provider = FakeProvider([])
    app, _ = _make_app(tmp_path, db_name="t3.db", provider=provider)
    with TestClient(app) as client:
        _load_sample(client)
        empty = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "   "},
        )
        assert empty.status_code == 422

        too_long = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "a" * 1001},
        )
        assert too_long.status_code == 422


def test_post_run_422_without_dataset(tmp_path) -> None:
    provider = FakeProvider([])
    app, _ = _make_app(tmp_path, db_name="t4.db", provider=provider)
    with TestClient(app) as client:
        post = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Why are customers waiting?"},
        )
        assert post.status_code == 422
        assert post.json()["detail"]["code"] == "no_dataset"


def test_run_persists_trace_blocks_warnings_and_model(tmp_path) -> None:
    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[ToolCall(name="get_backlog_analysis", arguments={})]),
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "finding",
                                "text": "Backlog has 999 tickets because routing failed.",
                                "evidence_call_ids": ["c1"],
                            }
                        ]
                    }
                ),
                model="gemini-test-model-v1",
            ),
        ],
        model_name="gemini-test-model-v1",
    )
    app, _ = _make_app(tmp_path, db_name="t5.db", provider=provider)
    with TestClient(app) as client:
        _load_sample(client)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Is the backlog a concern?"},
        ).json()["run_id"]
        final = _poll_until_done(client, 1, run_id)

        assert final["model"] == "gemini-test-model-v1"
        assert len(final["tool_trace"]) == 1
        assert final["tool_trace"][0]["call_id"] == "c1"
        assert len(final["answer_blocks"]) == 1
        codes = {w["code"] for w in final["warnings"]}
        assert "ungrounded_number" in codes
        assert "causal_wording_in_finding" in codes

        listed = client.get("/api/engagements/1/assistant/runs?limit=10")
        assert listed.status_code == 200
        runs = listed.json()
        assert len(runs) == 1
        assert runs[0]["id"] == run_id


class _BlockingProvider(LLMProvider):
    """Provider that pauses after the first tool call so tests can inspect live running state."""

    def __init__(self, first_call_done: threading.Event, release: threading.Event) -> None:
        self.model_name = "blocking-fake-model"
        self._step = 0
        self._first_call_done = first_call_done
        self._release = release

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        self._step += 1
        if self._step == 1:
            return LLMResponse(
                tool_calls=[ToolCall(name="get_agent_workload", arguments={})],
                model=self.model_name,
            )
        # Tool call c1 has now executed and been persisted to DB before round trip 2!
        self._first_call_done.set()
        self._release.wait(timeout=5.0)
        return LLMResponse(
            text=json.dumps(
                {
                    "blocks": [
                        {
                            "type": "finding",
                            "text": "Top 3 agents handled 40% of assigned tickets.",
                            "evidence_call_ids": ["c1"],
                        }
                    ]
                }
            ),
            model=self.model_name,
        )


def test_trace_visible_while_run_in_progress(tmp_path) -> None:
    first_done = threading.Event()
    release = threading.Event()
    provider = _BlockingProvider(first_done, release)
    app, _ = _make_app(tmp_path, db_name="t6.db", provider=provider)
    with TestClient(app) as client:
        _load_sample(client)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "How balanced is workload?"},
        ).json()["run_id"]

        assert first_done.wait(timeout=5.0)
        in_progress = client.get(f"/api/engagements/1/assistant/runs/{run_id}").json()
        assert in_progress["status"] == "running"
        assert len(in_progress["tool_trace"]) == 1
        assert in_progress["tool_trace"][0]["tool"] == "get_agent_workload"
        assert in_progress["tool_trace"][0]["ok"] is True

        release.set()
        final = _poll_until_done(client, 1, run_id)
        assert final["status"] == "completed"


def test_second_run_while_running_returns_409(tmp_path) -> None:
    first_done = threading.Event()
    release = threading.Event()
    provider = _BlockingProvider(first_done, release)
    app, _ = _make_app(tmp_path, db_name="t7.db", provider=provider)
    with TestClient(app) as client:
        _load_sample(client)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "First question"},
        ).json()["run_id"]

        assert first_done.wait(timeout=5.0)
        second = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Second overlapping question"},
        )
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "run_in_progress"

        release.set()
        _poll_until_done(client, 1, run_id)


def test_stale_running_runs_marked_failed_on_startup(tmp_path) -> None:
    db_name = "t8.db"
    app1, _ = _make_app(tmp_path, db_name=db_name, provider=FakeProvider([]))
    with TestClient(app1) as client1:
        ds_id = _load_sample(client1)
        with app1.state.session_factory() as session:
            stale = AgentRun(
                engagement_id=1,
                dataset_id=ds_id,
                question="Interrupted run",
                status=AgentRunStatus.running,
                answer_status=AnswerStatus.none,
                model="fake-model",
            )
            session.add(stale)
            session.commit()
            stale_id = stale.id

    # Restart app against the same SQLite DB
    app2, _ = _make_app(tmp_path, db_name=db_name, provider=FakeProvider([]))
    with TestClient(app2) as client2:
        resp = client2.get(f"/api/engagements/1/assistant/runs/{stale_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error"]["code"] == "interrupted"
        assert body["finished_at"] is not None


def test_run_of_other_engagement_returns_404(tmp_path) -> None:
    provider = FakeProvider(
        [
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "limitation",
                                "text": "No metrics requested.",
                                "evidence_call_ids": [],
                            }
                        ]
                    }
                )
            )
        ]
    )
    app, _ = _make_app(tmp_path, db_name="t9.db", provider=provider)
    with TestClient(app) as client:
        _load_sample(client, engagement_id=1)
        other = client.post(
            "/api/engagements",
            json={
                "name": "Second Engagement",
                "client_name": "Other Co",
                "industry": "Retail",
                "client_statement": "Testing isolation.",
            },
        )
        assert other.status_code == 201
        other_id = other.json()["id"]

        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Test isolation"},
        ).json()["run_id"]
        _poll_until_done(client, 1, run_id)

        assert (
            client.get(f"/api/engagements/{other_id}/assistant/runs/{run_id}").status_code
            == 404
        )
        assert (
            client.get("/api/engagements/999/assistant/runs/1").status_code == 404
        )
        assert (
            client.get(f"/api/engagements/1/assistant/runs/9999").status_code == 404
        )


def test_run_writes_audit_entry_without_secrets(tmp_path) -> None:
    secret = "SUPER_SECRET_API_KEY_AUDIT_TEST_777"
    provider = FakeProvider(
        [
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "clarifying_question",
                                "text": "Which category matters most?",
                                "evidence_call_ids": [],
                            }
                        ]
                    }
                )
            )
        ],
        model_name="audit-check-model",
    )
    app, _ = _make_app(
        tmp_path,
        db_name="t10.db",
        llm_api_key=secret,
        provider=provider,
    )
    with TestClient(app) as client:
        _load_sample(client)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Check audit log"},
        ).json()["run_id"]
        _poll_until_done(client, 1, run_id)

        with app.state.session_factory() as session:
            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.action == "assistant_question",
                    AuditLog.entity_id == str(run_id),
                )
                .first()
            )
            assert entry is not None
            assert entry.actor == "Demo operator"
            assert entry.details["run_id"] == run_id
            assert entry.details["model"] == "audit-check-model"
            assert secret not in json.dumps(entry.details)


def test_failed_run_persists_error_without_secrets(tmp_path) -> None:
    secret = "SUPER_SECRET_API_KEY_ERROR_TEST_888"
    provider = FakeProvider(
        [
            LLMProviderError(
                f"Upstream error using key={secret} Authorization: Bearer {secret}",
                secrets=(secret,),
            )
        ]
    )
    app, _ = _make_app(
        tmp_path,
        db_name="t11.db",
        llm_api_key=secret,
        provider=provider,
    )
    with TestClient(app) as client:
        _load_sample(client)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Trigger provider failure"},
        ).json()["run_id"]
        final = _poll_until_done(client, 1, run_id)

        assert final["status"] == "failed"
        assert final["error"] is not None
        assert final["error"]["code"] == "llm_provider_error"
        assert secret not in json.dumps(final)


def test_engagement_delete_removes_runs_but_dataset_delete_keeps_them(tmp_path) -> None:
    provider = FakeProvider(
        [
            LLMResponse(
                text=json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "limitation",
                                "text": "Scope check complete.",
                                "evidence_call_ids": [],
                            }
                        ]
                    }
                )
            )
        ]
    )
    app, _ = _make_app(tmp_path, db_name="t12.db", provider=provider)
    with TestClient(app) as client:
        ds_id = _load_sample(client, engagement_id=1)
        run_id = client.post(
            "/api/engagements/1/assistant/runs",
            json={"question": "Persist after dataset delete"},
        ).json()["run_id"]
        _poll_until_done(client, 1, run_id)

        # Delete dataset -> run MUST remain with dataset_id retained
        del_ds = client.delete(f"/api/engagements/1/datasets/{ds_id}")
        assert del_ds.status_code == 204
        still_there = client.get(f"/api/engagements/1/assistant/runs/{run_id}")
        assert still_there.status_code == 200
        assert still_there.json()["dataset_id"] == ds_id

        # Delete engagement -> run MUST be cascade-deleted
        del_eng = client.delete("/api/engagements/1")
        assert del_eng.status_code == 204
        with app.state.session_factory() as session:
            assert session.get(AgentRun, run_id) is None


def test_assistant_worker_unexpected_exception_logs_and_marks_failed(tmp_path, monkeypatch) -> None:
    from unittest.mock import patch

    provider = FakeProvider([], model_name="fake-model")
    app, _ = _make_app(tmp_path, db_name="t13_worker_fail.db", provider=provider)
    with patch("app.api.assistant.run_investigation", side_effect=RuntimeError("Unexpected worker failure")):
        with TestClient(app) as client:
            _load_sample(client, engagement_id=1)
            post = client.post(
                "/api/engagements/1/assistant/runs",
                json={"question": "Trigger worker exception"},
            )
            assert post.status_code == 202
            run_id = post.json()["run_id"]
            final = _poll_until_done(client, 1, run_id)
            assert final["status"] == "failed"
            assert final["error"]["code"] == "run_execution_error"
            assert "Unexpected worker failure" in final["error"]["message"]


def test_answer_status_values_are_a_closed_documented_set() -> None:
    expected = {"structured", "unstructured", "none"}
    actual = {e.value for e in AnswerStatus}
    assert actual == expected
    # Ensure no unsupported values exist in the enum
    assert "unsupported" not in actual
