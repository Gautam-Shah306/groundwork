"""Unit tests for the deterministic analysis tool registry (Part C)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.agent.tools import ToolRunContext, build_analysis_tool_registry
from app.api.diagnostics import get_diagnostics
from app.config import Settings
from app.db import create_db_engine, create_session_factory, init_db
from app.findings.rules import generate_findings
from app.ingest.service import ingest_csv_bytes
from app.metrics.config import load_metrics_config
from app.metrics.frame import load_ticket_frame
from app.metrics.registry import compute_all_metrics
from app.models import Dataset, Engagement, Ticket
from app.seed import seed_demo_data


@pytest.fixture()
def sample_context(tmp_path) -> tuple[Session, Engagement, Dataset, ToolRunContext]:
    db_url = f"sqlite:///{tmp_path.as_posix()}/tools_test.db"
    engine = create_db_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    seed_demo_data(session)
    engagement = session.query(Engagement).first()
    assert engagement is not None

    sample_path = Settings(_env_file=None).resolved_data_dir / "sample_tickets.csv"
    dataset = ingest_csv_bytes(
        session,
        engagement_id=engagement.id,
        filename="sample_tickets.csv",
        raw_bytes=sample_path.read_bytes(),
        is_sample=True,
    )
    ctx = ToolRunContext(db=session, engagement_id=engagement.id, dataset=dataset)
    yield session, engagement, dataset, ctx
    session.close()
    engine.dispose()


def test_registry_exposes_expected_tools_with_json_schemas(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    expected = [
        "get_ticket_summary",
        "get_response_metrics",
        "get_resolution_metrics",
        "get_category_breakdown",
        "get_agent_workload",
        "get_backlog_analysis",
        "get_findings",
    ]
    assert registry.tool_names == expected

    schemas = registry.schemas()
    assert [s.name for s in schemas] == expected
    for schema in schemas:
        assert schema.description
        assert schema.parameters_schema.get("type") == "object"
        assert schema.parameters_schema.get("additionalProperties") is False


def test_tool_rejects_unknown_arguments(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    res = registry.execute("get_agent_workload", {"unexpected_param": 123})
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "invalid_arguments"
    assert res.data is None


def test_tool_invalid_enum_returns_structured_error(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    res = registry.execute("get_response_metrics", {"metric": "made_up_metric"})
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "invalid_arguments"
    assert "made_up_metric" not in (res.data or {})


def test_unknown_tool_returns_structured_error(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    res = registry.execute("send_customer_email", {"ticket_id": "KL-000001"})
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "unknown_tool"
    assert "send_customer_email" in res.error.message


def test_tools_accept_no_dataset_or_engagement_id(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    for schema in registry.schemas():
        props = schema.parameters_schema.get("properties", {})
        assert "dataset_id" not in props
        assert "engagement_id" not in props

    for name in registry.tool_names:
        res_ds = registry.execute(name, {"dataset_id": 999})
        assert res_ds.ok is False
        assert res_ds.error is not None
        assert res_ds.error.code == "invalid_arguments"

        res_eng = registry.execute(name, {"engagement_id": 999})
        assert res_eng.ok is False
        assert res_eng.error is not None
        assert res_eng.error.code == "invalid_arguments"


def test_get_ticket_summary_matches_diagnostics_kpis(sample_context) -> None:
    session, engagement, dataset, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    diag = get_diagnostics(engagement.id, dataset.id, db=session)
    res = registry.execute("get_ticket_summary", {"volume_view": "by_band"})

    assert res.ok is True
    assert isinstance(res.data, dict)
    assert res.data["scope_summary"] == diag.scope_summary.model_dump(mode="json")

    diag_kpis = {k.metric_id: k.value for k in diag.kpis}
    tool_kpis = {k["metric_id"]: k["value"] for k in res.data["kpis"]}
    assert tool_kpis == diag_kpis
    assert res.data["volume_view"]["metric_id"] == "volume_by_band"
    assert res.data["volume_view"]["n_included"] == 1991


def test_get_response_metrics_returns_each_allowed_metric(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    allowed = [
        "first_response_time",
        "agent_response_time",
        "triage_time",
        "triage_share_of_first_response",
        "first_response_by_band",
        "sla_attainment",
        "factor_comparison",
    ]
    for metric_name in allowed:
        res = registry.execute("get_response_metrics", {"metric": metric_name})
        assert res.ok is True
        assert isinstance(res.data, dict)
        assert res.data["metric_id"] == metric_name
        assert res.data["definition"]
        assert res.data["scope"]
        assert "n_included" in res.data
        assert "exclusions" in res.data

    res_metric = registry.execute("get_resolution_metrics", {"metric": "resolution_time"})
    assert res_metric.ok is True
    assert isinstance(res_metric.data, dict)
    assert res_metric.data["metric_id"] == "resolution_time"


def test_get_category_breakdown_views_match_metrics(sample_context) -> None:
    session, engagement, dataset, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)
    diag = get_diagnostics(engagement.id, dataset.id, db=session)

    expected_map = {
        "volume": "volume_by_category",
        "delay_table": "category_delay_table",
        "reassignment": "reassignment_rate",
    }
    for view, metric_id in expected_map.items():
        res = registry.execute("get_category_breakdown", {"view": view})
        assert res.ok is True
        assert isinstance(res.data, dict)
        assert res.data["metric_id"] == metric_id
        assert res.data["data"] == diag.metrics[metric_id].data


def test_workload_and_backlog_tools_match_metrics(sample_context) -> None:
    session, engagement, dataset, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)
    diag = get_diagnostics(engagement.id, dataset.id, db=session)

    workload = registry.execute("get_agent_workload", {})
    assert workload.ok is True
    assert workload.data["metric_id"] == "agent_workload"
    assert workload.data["data"] == diag.metrics["agent_workload"].data

    backlog = registry.execute("get_backlog_analysis", {})
    assert backlog.ok is True
    assert backlog.data["metric_id"] == "backlog_ageing"
    assert backlog.data["data"] == diag.metrics["backlog_ageing"].data


def test_get_findings_matches_findings_module(sample_context) -> None:
    session, _, dataset, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)
    cfg = load_metrics_config()
    frame, as_of = load_ticket_frame(session, dataset.id, cfg)
    raw_metrics = compute_all_metrics(frame, cfg, as_of)
    expected_findings = generate_findings(raw_metrics, cfg)

    res = registry.execute("get_findings", {})
    assert res.ok is True
    assert isinstance(res.data, dict)
    assert [f["id"] for f in res.data["findings"]] == [f.id for f in expected_findings]
    assert [f["strength"] for f in res.data["findings"]] == [
        f.strength for f in expected_findings
    ]
    assert len(res.data["validation_questions"]) > 0


def test_large_result_truncated_with_flag_and_original_count(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path.as_posix()}/trunc_test.db"
    engine = create_db_engine(db_url)
    init_db(engine)
    session = create_session_factory(engine)()
    seed_demo_data(session)
    engagement = session.query(Engagement).first()
    assert engagement is not None

    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    dataset = Dataset(
        engagement_id=engagement.id,
        filename="long_period.csv",
        is_sample=False,
        record_count=75,
        period_start=start,
        period_end=start + timedelta(days=74),
        validation_report={},
    )
    session.add(dataset)
    session.flush()

    for i in range(75):
        created = start + timedelta(days=i)
        session.add(
            Ticket(
                ticket_id=f"T-{i:04d}",
                dataset_id=dataset.id,
                engagement_id=engagement.id,
                created_at=created,
                assigned_at=created + timedelta(hours=1),
                first_response_at=created + timedelta(hours=2),
                resolved_at=created + timedelta(hours=6),
                category="order_tracking",
                priority="medium",
                queue="Order support",
                assigned_agent="Agent 01",
                status="resolved",
                channel="email",
                reassignment_count=0,
                customer_id=f"CUST-{i:04d}",
                is_valid=True,
                validation_flags=[],
            )
        )
    session.commit()

    ctx = ToolRunContext(db=session, engagement_id=engagement.id, dataset=dataset)
    registry = build_analysis_tool_registry(ctx)
    res = registry.execute("get_ticket_summary", {"volume_view": "by_day"})

    assert res.ok is True
    assert res.truncated is True
    assert res.original_row_count == 75
    assert len(res.data["volume_view"]["data"]) == 60

    session.close()
    engine.dispose()


def test_tool_results_contain_no_row_level_ticket_data(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    calls = [
        ("get_ticket_summary", {"volume_view": "by_day"}),
        ("get_response_metrics", {"metric": "first_response_time"}),
        ("get_response_metrics", {"metric": "factor_comparison"}),
        ("get_resolution_metrics", {"metric": "resolution_time"}),
        ("get_category_breakdown", {"view": "delay_table"}),
        ("get_agent_workload", {}),
        ("get_backlog_analysis", {}),
        ("get_findings", {}),
    ]
    for name, args in calls:
        res = registry.execute(name, args)
        assert res.ok is True
        blob = json.dumps(res.data)
        assert "KL-000" not in blob
        assert "CUST-" not in blob
        assert "answer_key" not in blob.lower()


def test_call_ids_unique_and_sequential_within_run(sample_context) -> None:
    _, _, _, ctx = sample_context
    registry = build_analysis_tool_registry(ctx)

    r1 = registry.execute("get_ticket_summary", {})
    r2 = registry.execute("get_agent_workload", {})
    r3 = registry.execute("unknown_tool", {})
    r4 = registry.execute("get_backlog_analysis", {})

    assert [r1.call_id, r2.call_id, r3.call_id, r4.call_id] == ["c1", "c2", "c3", "c4"]
