"""Transactional CSV ingestion service storing Dataset, Tickets, and AuditLog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.ingest.parse import parse_csv_bytes
from app.ingest.validate import ValidationOutput, validate_parsed_csv
from app.models import Dataset, Ticket, utc_now
from app.triage.config import TriageConfig, load_triage_config


def _build_validation_report_json(
    validation: ValidationOutput,
    stored_tickets: list[Ticket],
) -> dict[str, Any]:
    checks_with_examples: list[dict[str, Any]] = []
    for check in validation.checks:
        code = check["code"]
        examples = [
            {
                "row_id": stored_tickets[idx].row_id,
                "ticket_id": stored_tickets[idx].ticket_id,
            }
            for idx in validation.example_indices_by_code.get(code, [])
        ]
        checks_with_examples.append({**check, "examples": examples})

    return {
        "record_count": validation.record_count,
        "period_start": validation.period_start.isoformat() if validation.period_start else None,
        "period_end": validation.period_end.isoformat() if validation.period_end else None,
        "distinct_ticket_ids": validation.distinct_ticket_ids,
        "distinct_customers": validation.distinct_customers,
        "dataset_warnings": validation.dataset_warnings,
        "checks": checks_with_examples,
        "rows_valid_for_all_metrics": validation.rows_valid_for_all_metrics,
        "excluded_by_scope": validation.excluded_by_scope,
    }


def _persist_tickets(
    db: Session,
    *,
    dataset: Dataset,
    engagement_id: int,
    validation: ValidationOutput,
) -> list[Ticket]:
    tickets = [
        Ticket(
            ticket_id=row.ticket_id,
            engagement_id=engagement_id,
            dataset_id=dataset.id,
            created_at=row.created_at,
            assigned_at=row.assigned_at,
            first_response_at=row.first_response_at,
            resolved_at=row.resolved_at,
            category=row.category,
            priority=row.priority,
            queue=row.queue,
            assigned_agent=row.assigned_agent,
            status=row.status,
            channel=row.channel,
            reassignment_count=row.reassignment_count,
            customer_id=row.customer_id,
            is_valid=row.is_valid,
            validation_flags=row.validation_flags,
        )
        for row in validation.rows
    ]
    db.add_all(tickets)
    db.flush()
    return tickets


def ingest_csv_bytes(
    db: Session,
    *,
    engagement_id: int,
    raw_bytes: bytes,
    filename: str,
    is_sample: bool = False,
    triage_config: TriageConfig | None = None,
) -> Dataset:
    """Parse, validate, and atomically store a CSV dataset and all of its ticket rows."""
    parsed = parse_csv_bytes(raw_bytes, filename)
    config = triage_config if triage_config is not None else load_triage_config()
    validation = validate_parsed_csv(parsed, config)

    clean_filename = Path(filename).name
    try:
        dataset = Dataset(
            engagement_id=engagement_id,
            filename=clean_filename,
            is_sample=is_sample,
            uploaded_at=utc_now(),
            record_count=validation.record_count,
            period_start=validation.period_start,
            period_end=validation.period_end,
            validation_report={},
        )
        db.add(dataset)
        db.flush()

        stored_tickets = _persist_tickets(
            db,
            dataset=dataset,
            engagement_id=engagement_id,
            validation=validation,
        )
        dataset.validation_report = _build_validation_report_json(validation, stored_tickets)

        record_audit_event(
            db,
            engagement_id=engagement_id,
            action="load_sample" if is_sample else "upload",
            entity_type="dataset",
            entity_id=dataset.id,
            details={
                "dataset_id": dataset.id,
                "filename": dataset.filename,
                "record_count": dataset.record_count,
                "is_sample": is_sample,
            },
        )
        db.commit()
        db.refresh(dataset)
        return dataset
    except Exception:
        db.rollback()
        raise
