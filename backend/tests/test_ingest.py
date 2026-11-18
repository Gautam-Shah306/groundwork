"""Tests for CSV upload, validation pipeline, sample dataset loading, and row drill-down."""

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
from app.ingest.parse import MAX_FILE_SIZE_BYTES, MAX_ROWS, REQUIRED_COLUMNS
from app.main import create_app
from app.models import AuditLog, Dataset, Ticket

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ingest_client(tmp_path: Path) -> Generator[tuple[TestClient, Any, int], None, None]:
    db_file = tmp_path / "test_ingest.db"
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
                "name": "Ingest Test Engagement",
                "client_name": "Kora Living",
                "industry": "Retail",
                "stage": "diagnose",
            },
        ).json()
        yield client, application, eng["id"]


def _base_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticket_id": "KL-000001",
        "created_at": "2026-09-10T10:00:00+05:30",
        "assigned_at": "2026-09-10T12:00:00+05:30",
        "first_response_at": "2026-09-10T13:00:00+05:30",
        "resolved_at": "2026-09-11T10:00:00+05:30",
        "category": "order_tracking",
        "priority": "medium",
        "queue": "Order support",
        "assigned_agent": "Agent 01",
        "status": "resolved",
        "channel": "email",
        "reassignment_count": "0",
        "customer_id": "CUST-0001",
    }
    row.update(overrides)
    return row


def _make_csv_bytes(
    rows: list[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    bom: bool = False,
) -> bytes:
    fieldnames = columns if columns is not None else list(REQUIRED_COLUMNS)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    encoding = "utf-8-sig" if bom else "utf-8"
    return buf.getvalue().encode(encoding)


def _upload(
    client: TestClient,
    engagement_id: int,
    raw: bytes,
    filename: str = "tickets.csv",
    content_type: str = "text/csv",
):
    return client.post(
        f"/api/engagements/{engagement_id}/datasets",
        files={"file": (filename, raw, content_type)},
    )


def _check_map(dataset_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["code"]: c for c in dataset_payload["validation_report"]["checks"]}


def test_upload_valid_csv_stores_all_rows_and_report(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(ticket_id="KL-000001", customer_id="CUST-0001"),
            _base_row(
                ticket_id="KL-000002",
                created_at="2026-09-12T11:00:00+05:30",
                assigned_at="2026-09-12T13:00:00+05:30",
                first_response_at="2026-09-12T14:00:00+05:30",
                resolved_at="2026-09-13T11:00:00+05:30",
                customer_id="CUST-0002",
            ),
        ]
    )

    resp = _upload(client, eng_id, raw, filename="clean.csv")

    assert resp.status_code == 201
    ds = resp.json()
    assert ds["filename"] == "clean.csv"
    assert ds["is_sample"] is False
    assert ds["is_active"] is True
    assert ds["record_count"] == 2
    report = ds["validation_report"]
    assert report["rows_valid_for_all_metrics"] == 2
    assert report["distinct_ticket_ids"] == 2
    assert report["distinct_customers"] == 2
    assert report["excluded_by_scope"] == {
        "all_metrics": 0,
        "response_metrics": 0,
        "resolution_metrics": 0,
        "triage_metrics": 0,
    }


def test_upload_rejects_non_csv_extension(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row()])

    resp = _upload(client, eng_id, raw, filename="tickets.txt", content_type="text/csv")

    assert resp.status_code == 422
    assert ".csv" in str(resp.json()["detail"]).lower()


def test_upload_rejects_empty_file(ingest_client) -> None:
    client, _, eng_id = ingest_client

    resp = _upload(client, eng_id, b"", filename="empty.csv")

    assert resp.status_code == 422
    assert "empty" in str(resp.json()["detail"]).lower()


def test_upload_rejects_file_over_size_limit(ingest_client) -> None:
    client, _, eng_id = ingest_client
    oversized = b"a" * (MAX_FILE_SIZE_BYTES + 10)

    resp = _upload(client, eng_id, oversized, filename="huge.csv")

    assert resp.status_code == 422
    assert "10 mb" in str(resp.json()["detail"]).lower()


def test_upload_rejects_more_than_50000_rows(ingest_client) -> None:
    client, _, eng_id = ingest_client
    header = ",".join(REQUIRED_COLUMNS) + "\n"
    line = "KL-1,2026-09-10T10:00:00+05:30,,,,,,,,,,,\n"
    raw = (header + line * (MAX_ROWS + 1)).encode("utf-8")
    assert len(raw) < MAX_FILE_SIZE_BYTES

    resp = _upload(client, eng_id, raw, filename="too_many.csv")

    assert resp.status_code == 422
    assert "50,000" in str(resp.json()["detail"])


def test_upload_rejects_missing_required_columns_and_stores_nothing(ingest_client) -> None:
    client, application, eng_id = ingest_client
    bad_cols = [c for c in REQUIRED_COLUMNS if c != "category"] + ["mystery_col"]
    raw = _make_csv_bytes([_base_row(mystery_col="abc")], columns=bad_cols)

    resp = _upload(client, eng_id, raw, filename="missing_col.csv")

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "category" in detail["missing_columns"]
    assert "mystery_col" in detail["unexpected_columns"]

    with application.state.session_factory() as db:
        assert db.scalars(select(Dataset)).all() == []
        assert db.scalars(select(Ticket)).all() == []


def test_upload_extra_columns_ignored_with_warning(ingest_client) -> None:
    client, _, eng_id = ingest_client
    cols = list(REQUIRED_COLUMNS) + ["internal_note", "region_code"]
    raw = _make_csv_bytes(
        [_base_row(internal_note="ignore me", region_code="IN-KA")],
        columns=cols,
    )

    resp = _upload(client, eng_id, raw, filename="extra_cols.csv")

    assert resp.status_code == 201
    warnings = resp.json()["validation_report"]["dataset_warnings"]
    extra_warn = next(w for w in warnings if w["code"] == "extra_columns_ignored")
    assert extra_warn["columns"] == ["internal_note", "region_code"]


def test_upload_handles_utf8_bom(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row()], bom=True)
    assert raw.startswith(b"\xef\xbb\xbf")

    resp = _upload(client, eng_id, raw, filename="bom.csv")

    assert resp.status_code == 201
    assert resp.json()["record_count"] == 1


def test_upload_non_utf8_returns_clear_error(ingest_client) -> None:
    client, _, eng_id = ingest_client
    bad_bytes = b"\xff\xfe\x00\x00not-utf8"

    resp = _upload(client, eng_id, bad_bytes, filename="latin.csv")

    assert resp.status_code == 422
    assert "utf-8" in str(resp.json()["detail"]).lower()


def test_whitespace_trimmed_and_vocabulary_lowercased_but_ids_keep_case(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                ticket_id="  KL-AbC-01  ",
                customer_id="  Cust-XyZ-99  ",
                category="  ORDER_TRACKING ",
                status=" Resolved ",
                channel=" WhatsApp ",
                priority=" HIGH ",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="norm.csv")
    assert resp.status_code == 201
    ds_id = resp.json()["id"]

    rows = client.get(f"/api/engagements/{eng_id}/datasets/{ds_id}/rows").json()["items"]
    assert len(rows) == 1
    row = rows[0]
    assert row["ticket_id"] == "KL-AbC-01"
    assert row["customer_id"] == "Cust-XyZ-99"
    assert row["category"] == "order_tracking"
    assert row["status"] == "resolved"
    assert row["channel"] == "whatsapp"
    assert row["priority"] == "high"
    assert row["is_valid"] is True


def test_cell_starting_with_formula_char_stored_as_plain_text(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                ticket_id="=SUM(1,2)",
                customer_id="@cmd('calc')",
                queue="+1+1",
                assigned_agent="-Agent01",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="formulas.csv")
    assert resp.status_code == 201
    ds_id = resp.json()["id"]

    rows = client.get(f"/api/engagements/{eng_id}/datasets/{ds_id}/rows").json()["items"]
    assert rows[0]["ticket_id"] == "=SUM(1,2)"
    assert rows[0]["customer_id"] == "@cmd('calc')"
    assert rows[0]["queue"] == "+1+1"
    assert rows[0]["assigned_agent"] == "-Agent01"


def test_timestamps_without_offset_assumed_ist_with_dataset_warning(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                created_at="2026-09-10T10:00:00",
                assigned_at="2026-09-10T12:00:00",
                first_response_at="2026-09-10T13:00:00",
                resolved_at="2026-09-11T10:00:00",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="naive_ts.csv")
    assert resp.status_code == 201
    ds = resp.json()
    warnings = ds["validation_report"]["dataset_warnings"]
    tz_warn = next(w for w in warnings if w["code"] == "timestamps_without_timezone")
    assert tz_warn["count"] == 4

    rows = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/rows").json()["items"]
    # 10:00:00 IST (+05:30) == 04:30:00Z UTC
    assert rows[0]["created_at"].startswith("2026-09-10T04:30:00")


def test_unparseable_timestamp_flagged_and_row_invalid(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row(created_at="not-a-timestamp")])

    resp = _upload(client, eng_id, raw, filename="bad_ts.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["missing_or_invalid_created_at"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 0

    rows = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/rows").json()["items"]
    assert rows[0]["is_valid"] is False
    assert any(f["code"] == "missing_or_invalid_created_at" for f in rows[0]["validation_flags"])


def test_duplicate_ids_flag_only_second_occurrence(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(ticket_id="KL-DUP-1"),
            _base_row(ticket_id="KL-DUP-1"),
            _base_row(ticket_id="KL-DUP-1"),
        ]
    )

    resp = _upload(client, eng_id, raw, filename="dups.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["duplicate_ticket_id"]["count"] == 2
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 1

    rows = client.get(f"/api/engagements/{eng_id}/datasets/{ds['id']}/rows").json()["items"]
    assert rows[0]["is_valid"] is True
    assert rows[0]["validation_flags"] == []
    assert rows[1]["is_valid"] is False
    assert rows[2]["is_valid"] is False


def test_unknown_category_flagged_and_row_invalid(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row(category="billing_misc")])

    resp = _upload(client, eng_id, raw, filename="bad_cat.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["unknown_category"]["count"] == 1
    assert checks["unknown_category"]["affects"] == ["all_metrics"]
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 0


def test_first_response_before_created_affects_response_only(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                created_at="2026-09-10T10:00:00+05:30",
                assigned_at="2026-09-10T11:00:00+05:30",
                first_response_at="2026-09-10T09:30:00+05:30",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="frt_before.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["first_response_before_created"]["count"] == 1
    assert checks["assignment_order_inconsistent"]["count"] == 0
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"] == {
        "all_metrics": 0,
        "response_metrics": 1,
        "resolution_metrics": 0,
        "triage_metrics": 0,
    }


def test_resolved_without_first_response_flagged_response_only(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row(status="resolved", first_response_at="")])

    resp = _upload(client, eng_id, raw, filename="no_frt.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["missing_first_response_on_resolved"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"]["response_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"]["resolution_metrics"] == 0
    assert ds["validation_report"]["excluded_by_scope"]["triage_metrics"] == 0


def test_resolved_without_resolved_at_flagged_resolution_only(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row(status="resolved", resolved_at="")])

    resp = _upload(client, eng_id, raw, filename="no_res.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["missing_resolved_at_on_resolved"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"]["resolution_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"]["response_metrics"] == 0
    assert ds["validation_report"]["excluded_by_scope"]["triage_metrics"] == 0


def test_resolved_before_created_and_implausible_duration_flagged(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                ticket_id="KL-RES-EARLY",
                created_at="2026-09-10T10:00:00+05:30",
                resolved_at="2026-09-09T10:00:00+05:30",
            ),
            _base_row(
                ticket_id="KL-RES-LONG",
                created_at="2026-09-10T10:00:00+05:30",
                resolved_at="2027-06-01T10:00:00+05:30",
            ),
        ]
    )

    resp = _upload(client, eng_id, raw, filename="res_issues.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["resolved_before_created"]["count"] == 1
    assert checks["implausible_duration"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 2
    assert ds["validation_report"]["excluded_by_scope"]["resolution_metrics"] == 2


def test_assignment_order_and_missing_assignment_flagged_triage_only(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                ticket_id="KL-ASSIGN-EARLY",
                created_at="2026-09-10T10:00:00+05:30",
                assigned_at="2026-09-10T09:00:00+05:30",
            ),
            _base_row(
                ticket_id="KL-ASSIGN-LATE",
                created_at="2026-09-10T10:00:00+05:30",
                assigned_at="2026-09-10T15:00:00+05:30",
                first_response_at="2026-09-10T13:00:00+05:30",
            ),
            _base_row(
                ticket_id="KL-ASSIGN-HALF",
                assigned_at="",
                assigned_agent="Agent 02",
            ),
        ]
    )

    resp = _upload(client, eng_id, raw, filename="triage_issues.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["assignment_order_inconsistent"]["count"] == 2
    assert checks["missing_assignment"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 3
    assert ds["validation_report"]["excluded_by_scope"] == {
        "all_metrics": 0,
        "response_metrics": 0,
        "resolution_metrics": 0,
        "triage_metrics": 3,
    }


def test_open_ticket_with_resolved_at_flagged(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                ticket_id="KL-OPEN-RES",
                status="open",
                resolved_at="2026-09-11T10:00:00+05:30",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="open_res.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["resolved_at_on_unresolved_status"]["count"] == 1
    assert ds["validation_report"]["excluded_by_scope"]["resolution_metrics"] == 1


def test_unknown_status_channel_priority_warn_but_row_stays_valid(ingest_client) -> None:
    client, _, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(
                status="escalated_custom",
                channel="instagram_dm",
                priority="p0_urgent",
            )
        ]
    )

    resp = _upload(client, eng_id, raw, filename="vocab_warn.csv")
    assert resp.status_code == 201
    ds = resp.json()
    checks = _check_map(ds)
    assert checks["unknown_status"]["count"] == 1
    assert checks["unknown_channel"]["count"] == 1
    assert checks["unknown_priority"]["count"] == 1
    assert ds["validation_report"]["rows_valid_for_all_metrics"] == 1
    assert ds["validation_report"]["excluded_by_scope"] == {
        "all_metrics": 0,
        "response_metrics": 0,
        "resolution_metrics": 0,
        "triage_metrics": 0,
    }


def test_invalid_rows_are_stored_not_dropped(ingest_client) -> None:
    client, application, eng_id = ingest_client
    raw = _make_csv_bytes(
        [
            _base_row(ticket_id="KL-1"),
            _base_row(ticket_id="KL-1"),
            _base_row(ticket_id="KL-2", category="billing_misc"),
            _base_row(ticket_id="KL-3", created_at="bad-date"),
        ]
    )

    resp = _upload(client, eng_id, raw, filename="keep_all.csv")
    assert resp.status_code == 201
    ds_id = resp.json()["id"]

    with application.state.session_factory() as db:
        stored = db.scalars(select(Ticket).where(Ticket.dataset_id == ds_id)).all()
    assert len(stored) == 4
    assert sum(1 for r in stored if r.is_valid) == 1
    assert sum(1 for r in stored if not r.is_valid) == 3


def test_failed_upload_leaves_no_partial_dataset(ingest_client, monkeypatch) -> None:
    client, application, eng_id = ingest_client
    raw = _make_csv_bytes([_base_row()])

    def _boom(*_args, **_kwargs):
        raise RuntimeError("Simulated database failure mid-insert")

    monkeypatch.setattr("app.ingest.service._persist_tickets", _boom)

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        _upload(client, eng_id, raw, filename="boom.csv")

    with application.state.session_factory() as db:
        assert db.scalars(select(Dataset)).all() == []
        assert db.scalars(select(Ticket)).all() == []


def test_sample_load_matches_planted_issue_counts(ingest_client) -> None:
    client, _, eng_id = ingest_client

    resp = client.post(f"/api/engagements/{eng_id}/datasets/sample")

    assert resp.status_code == 201
    ds = resp.json()
    assert ds["filename"] == "sample_tickets.csv"
    assert ds["is_sample"] is True
    assert ds["is_active"] is True
    assert ds["record_count"] == 2000

    report = ds["validation_report"]
    assert report["rows_valid_for_all_metrics"] == 1991
    checks = _check_map(ds)
    assert checks["duplicate_ticket_id"]["count"] == 3
    assert checks["unknown_category"]["count"] == 6
    assert checks["first_response_before_created"]["count"] == 8
    assert checks["missing_first_response_on_resolved"]["count"] == 12
    assert checks["missing_resolved_at_on_resolved"]["count"] == 9
    assert checks["implausible_duration"]["count"] == 4

    # Verify no unexpected natural flags fired on the clean sample rows.
    for other_code in (
        "missing_or_invalid_created_at",
        "resolved_before_created",
        "assignment_order_inconsistent",
        "missing_assignment",
        "resolved_at_on_unresolved_status",
        "unknown_status",
        "unknown_channel",
        "unknown_priority",
    ):
        assert checks[other_code]["count"] == 0, f"Unexpected count for {other_code}"


def test_dataset_list_active_flag_and_ordering(ingest_client) -> None:
    client, _, eng_id = ingest_client
    first = _upload(client, eng_id, _make_csv_bytes([_base_row()]), filename="first.csv").json()
    second = _upload(client, eng_id, _make_csv_bytes([_base_row()]), filename="second.csv").json()

    items = client.get(f"/api/engagements/{eng_id}/datasets").json()
    assert [item["id"] for item in items] == [second["id"], first["id"]]
    assert items[0]["is_active"] is True
    assert items[1]["is_active"] is False


def test_rows_endpoint_paginates_and_filters_by_flag(ingest_client) -> None:
    client, _, eng_id = ingest_client
    rows_input = [
        _base_row(ticket_id=f"KL-OK-{i}") for i in range(5)
    ] + [
        _base_row(ticket_id=f"KL-BAD-{i}", category="billing_misc") for i in range(4)
    ]
    ds = _upload(client, eng_id, _make_csv_bytes(rows_input), filename="page.csv").json()

    page1 = client.get(
        f"/api/engagements/{eng_id}/datasets/{ds['id']}/rows?flag=unknown_category&page=1&page_size=2"
    ).json()
    page2 = client.get(
        f"/api/engagements/{eng_id}/datasets/{ds['id']}/rows?flag=unknown_category&page=2&page_size=2"
    ).json()

    assert page1["total"] == 4
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert [r["ticket_id"] for r in page1["items"]] == ["KL-BAD-0", "KL-BAD-1"]
    assert [r["ticket_id"] for r in page2["items"]] == ["KL-BAD-2", "KL-BAD-3"]


def test_dataset_of_other_engagement_returns_404(ingest_client) -> None:
    client, _, eng_id = ingest_client
    ds = _upload(client, eng_id, _make_csv_bytes([_base_row()]), filename="owned.csv").json()

    other_eng = client.post(
        "/api/engagements",
        json={"name": "Other Engagement", "client_name": "Other Co"},
    ).json()

    assert client.get(f"/api/engagements/{other_eng['id']}/datasets/{ds['id']}").status_code == 404
    assert (
        client.get(f"/api/engagements/{other_eng['id']}/datasets/{ds['id']}/rows").status_code == 404
    )
    assert (
        client.delete(f"/api/engagements/{other_eng['id']}/datasets/{ds['id']}").status_code == 404
    )


def test_delete_dataset_cascades_tickets_and_writes_audit(ingest_client) -> None:
    client, application, eng_id = ingest_client
    ds = _upload(client, eng_id, _make_csv_bytes([_base_row()]), filename="to_delete.csv").json()

    del_resp = client.delete(f"/api/engagements/{eng_id}/datasets/{ds['id']}")
    assert del_resp.status_code == 204

    with application.state.session_factory() as db:
        assert db.get(Dataset, ds["id"]) is None
        assert db.scalars(select(Ticket).where(Ticket.dataset_id == ds["id"])).all() == []
        logs = db.scalars(
            select(AuditLog)
            .where(
                AuditLog.engagement_id == eng_id,
                AuditLog.entity_type == "dataset",
                AuditLog.action == "delete",
            )
        ).all()
        assert len(logs) == 1
        assert logs[0].details["filename"] == "to_delete.csv"
        assert logs[0].details["record_count"] == 1


def test_upload_and_sample_write_audit_entries(ingest_client) -> None:
    client, application, eng_id = ingest_client
    _upload(client, eng_id, _make_csv_bytes([_base_row()]), filename="manual.csv")
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    with application.state.session_factory() as db:
        logs = db.scalars(
            select(AuditLog)
            .where(AuditLog.engagement_id == eng_id, AuditLog.entity_type == "dataset")
            .order_by(AuditLog.id.asc())
        ).all()

    assert [(entry.action, entry.details["filename"], entry.details["record_count"]) for entry in logs] == [
        ("upload", "manual.csv", 1),
        ("load_sample", "sample_tickets.csv", 2000),
    ]


def test_ingest_code_never_references_answer_key() -> None:
    ingest_dir = REPO_ROOT / "backend" / "app" / "ingest"
    datasets_api = REPO_ROOT / "backend" / "app" / "api" / "datasets.py"
    files_to_check = list(ingest_dir.rglob("*.py")) + [datasets_api]

    for py_file in files_to_check:
        assert "answer_key" not in py_file.read_text(encoding="utf-8")
