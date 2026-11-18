"""Integration tests for GET /api/engagements/{id}/datasets/{dataset_id}/diagnostics."""

from __future__ import annotations

import csv
import io
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.ingest.parse import REQUIRED_COLUMNS
from app.main import create_app
from app.models import AuditLog


@pytest.fixture()
def diag_client(tmp_path: Path) -> Generator[tuple[TestClient, Any, int], None, None]:
    db_file = tmp_path / "test_diag.db"
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        database_url=f"sqlite:///{db_file.as_posix()}",
        seed_on_start=False,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        eng = client.post(
            "/api/engagements",
            json={
                "name": "Diagnostics API Engagement",
                "client_name": "Kora Living",
                "stage": "diagnose",
            },
        ).json()
        yield client, application, eng["id"]


def _upload_csv(client: TestClient, eng_id: int, rows: list[dict[str, Any]], filename: str = "ds.csv") -> dict:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(REQUIRED_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in REQUIRED_COLUMNS})
    resp = client.post(
        f"/api/engagements/{eng_id}/datasets",
        files={"file": (filename, buf.getvalue().encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()


def test_diagnostics_returns_kpis_metrics_and_findings(diag_client) -> None:
    client, application, eng_id = diag_client
    ds = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()

    with application.state.session_factory() as db:
        audit_before = len(db.scalars(select(AuditLog)).all())

    resp = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/diagnostics")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["dataset"]["id"] == ds["id"]
    assert payload["timezone"] == "Asia/Kolkata"
    assert len(payload["kpis"]) == 6
    assert "first_response_time" in payload["metrics"]
    assert "factor_comparison" in payload["metrics"]
    assert len(payload["findings"]) >= 5
    assert len(payload["validation_questions"]) >= 3

    # Read-only: must not write audit log entries.
    with application.state.session_factory() as db:
        audit_after = len(db.scalars(select(AuditLog)).all())
    assert audit_after == audit_before


def test_diagnostics_kpis_have_no_target_fields(diag_client) -> None:
    client, _, eng_id = diag_client
    ds = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()

    payload = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/diagnostics").json()
    for kpi in payload["kpis"]:
        assert "target" not in kpi
        assert "improvement" not in kpi
        assert "improvement_pct" not in kpi


def test_diagnostics_404_for_unknown_engagement_unknown_dataset_and_cross_engagement(
    diag_client,
) -> None:
    client, _, eng_id = diag_client
    ds = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()
    other_eng = client.post(
        "/api/engagements",
        json={"name": "Other Eng", "client_name": "Other Co"},
    ).json()

    assert client.get(f"/api/engagements/99999/datasets/{ds['id']}/diagnostics").status_code == 404
    assert client.get(f"/api/engagements/{eng_id}/datasets/99999/diagnostics").status_code == 404
    assert (
        client.get(f"/api/engagements/{other_eng['id']}/datasets/{ds['id']}/diagnostics").status_code
        == 404
    )


def test_diagnostics_for_dataset_with_no_valid_rows_returns_empty_structures(
    diag_client,
) -> None:
    client, _, eng_id = diag_client
    ds = _upload_csv(
        client,
        eng_id,
        [
            {
                "ticket_id": "KL-BAD",
                "created_at": "2026-09-10T10:00:00+05:30",
                "assigned_at": "2026-09-10T12:00:00+05:30",
                "first_response_at": "2026-09-10T13:00:00+05:30",
                "resolved_at": "2026-09-11T10:00:00+05:30",
                "category": "billing_misc",
                "priority": "low",
                "queue": "General",
                "assigned_agent": "Agent 01",
                "status": "resolved",
                "channel": "email",
                "reassignment_count": "0",
                "customer_id": "CUST-1",
            }
        ],
        filename="all_invalid.csv",
    )

    resp = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/diagnostics")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["scope_summary"]["rows_valid_for_all_metrics"] == 0
    assert payload["metrics"]["first_response_time"]["data"]["n"] == 0
    assert payload["metrics"]["first_response_time"]["data"]["median"] is None
    assert payload["metrics"]["backlog_ageing"]["data"]["total_open_backlog"] == 0


def test_sample_metrics_are_in_expected_ranges(diag_client) -> None:
    client, _, eng_id = diag_client
    ds = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()
    payload = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/diagnostics").json()

    metrics = payload["metrics"]
    triage_share = metrics["triage_share_of_first_response"]["data"]["share"]
    assert 0.45 <= triage_share <= 0.75

    bands = {r["band"]: r for r in metrics["first_response_by_band"]["data"]}
    assert bands["evening"]["median"] - bands["afternoon"]["median"] >= 1.0

    by_cat = metrics["reassignment_rate"]["data"]["by_category"]
    or_rows = [r for r in by_cat if r["category"] in ("order_tracking", "returns_refunds")]
    other_rows = [r for r in by_cat if r["category"] not in ("order_tracking", "returns_refunds")]
    or_rate = sum(r["reassigned_count"] for r in or_rows) / sum(r["n"] for r in or_rows)
    other_rate = sum(r["reassigned_count"] for r in other_rows) / sum(r["n"] for r in other_rows)
    assert or_rate >= 3.0 * other_rate

    top3_share = metrics["agent_workload"]["data"]["top_n_share"]
    assert 0.35 <= top3_share <= 0.45

    assert (
        payload["scope_summary"]["rows_valid_for_all_metrics"]
        == ds["validation_report"]["rows_valid_for_all_metrics"]
    )


def test_sample_exclusion_counts_match_validation_report(diag_client) -> None:
    client, _, eng_id = diag_client
    ds = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()
    payload = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/diagnostics").json()

    expected = ds["validation_report"]["excluded_by_scope"]
    assert payload["metrics"]["first_response_time"]["n_excluded"] == expected["response_metrics"]
    assert payload["metrics"]["resolution_time"]["n_excluded"] == expected["resolution_metrics"]
    assert payload["metrics"]["triage_time"]["n_excluded"] == expected["triage_metrics"]
    assert payload["scope_summary"]["excluded_by_scope"] == expected
