"""Dataset upload, sample load, validation report, row drill-down, and delete APIs."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.audit import record_audit_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingest.parse import CSVParseError, MAX_FILE_SIZE_BYTES
from app.ingest.service import ingest_csv_bytes
from app.models import Dataset, Ticket
from app.schemas import DatasetResponse, DatasetRowsResponse, TicketRowResponse

router = APIRouter(prefix="/api/engagements/{engagement_id}/datasets", tags=["datasets"])


def _resolve_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, Settings):
        return configured
    return get_settings()


def _get_active_dataset_id(db: Session, engagement_id: int) -> int | None:
    return db.scalar(
        select(Dataset.id)
        .where(Dataset.engagement_id == engagement_id)
        .order_by(Dataset.uploaded_at.desc(), Dataset.id.desc())
        .limit(1)
    )


def _get_dataset_or_404(db: Session, engagement_id: int, dataset_id: int) -> Dataset:
    get_engagement_or_404(db, engagement_id)
    dataset = db.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.engagement_id == engagement_id,
        )
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found for engagement {engagement_id}.",
        )
    return dataset


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[DatasetResponse]:
    """List datasets for an engagement, newest first, marking the active dataset."""
    get_engagement_or_404(db, engagement_id)
    datasets = db.scalars(
        select(Dataset)
        .where(Dataset.engagement_id == engagement_id)
        .order_by(Dataset.uploaded_at.desc(), Dataset.id.desc())
    ).all()
    active_id = datasets[0].id if datasets else None
    return [
        DatasetResponse.from_orm_model(ds, is_active=(ds.id == active_id))
        for ds in datasets
    ]


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    engagement_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Upload and validate a CSV dataset for an engagement."""
    get_engagement_or_404(db, engagement_id)
    # Read at most MAX_FILE_SIZE_BYTES + 1 so oversized uploads fail fast without huge memory spikes.
    raw_bytes = await file.read(MAX_FILE_SIZE_BYTES + 1)
    filename = file.filename or ""

    try:
        dataset = ingest_csv_bytes(
            db,
            engagement_id=engagement_id,
            raw_bytes=raw_bytes,
            filename=filename,
            is_sample=False,
        )
    except CSVParseError as exc:
        detail: dict | str = (
            {"message": exc.message, **exc.details} if exc.details else exc.message
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        ) from exc

    return DatasetResponse.from_orm_model(dataset, is_active=True)


@router.post("/sample", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def load_sample_dataset(
    engagement_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Load data/sample_tickets.csv through the exact same ingestion and validation pipeline."""
    get_engagement_or_404(db, engagement_id)
    settings = _resolve_settings(request)
    sample_path = settings.resolved_data_dir / "sample_tickets.csv"
    if not sample_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample dataset data/sample_tickets.csv was not found on the server.",
        )

    raw_bytes = sample_path.read_bytes()
    try:
        dataset = ingest_csv_bytes(
            db,
            engagement_id=engagement_id,
            raw_bytes=raw_bytes,
            filename="sample_tickets.csv",
            is_sample=True,
        )
    except CSVParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.message,
        ) from exc

    return DatasetResponse.from_orm_model(dataset, is_active=True)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    engagement_id: int,
    dataset_id: int,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Return a single dataset with its full validation report."""
    dataset = _get_dataset_or_404(db, engagement_id, dataset_id)
    active_id = _get_active_dataset_id(db, engagement_id)
    return DatasetResponse.from_orm_model(dataset, is_active=(dataset.id == active_id))


@router.get("/{dataset_id}/rows", response_model=DatasetRowsResponse)
def list_dataset_rows(
    engagement_id: int,
    dataset_id: int,
    flag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DatasetRowsResponse:
    """Return paginated stored Ticket rows, optionally filtered by validation flag code."""
    _get_dataset_or_404(db, engagement_id, dataset_id)

    all_rows = db.scalars(
        select(Ticket)
        .where(
            Ticket.dataset_id == dataset_id,
            Ticket.engagement_id == engagement_id,
        )
        .order_by(Ticket.row_id.asc())
    ).all()

    if flag:
        filtered = [
            row
            for row in all_rows
            if any(isinstance(f, dict) and f.get("code") == flag for f in (row.validation_flags or []))
        ]
    else:
        filtered = list(all_rows)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return DatasetRowsResponse(
        dataset_id=dataset_id,
        flag=flag,
        page=page,
        page_size=page_size,
        total=total,
        items=[TicketRowResponse.from_orm_model(item) for item in page_items],
    )


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    engagement_id: int,
    dataset_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a dataset, cascade to all stored Ticket rows, and write an AuditLog entry."""
    dataset = _get_dataset_or_404(db, engagement_id, dataset_id)
    snapshot = {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "record_count": dataset.record_count,
    }
    db.delete(dataset)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="delete",
        entity_type="dataset",
        entity_id=dataset_id,
        details=snapshot,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
