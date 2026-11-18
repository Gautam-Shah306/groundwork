"""Pure CSV parsing, size/row limits, schema checks, and cell normalisation."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROWS = 50_000

REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticket_id",
    "created_at",
    "assigned_at",
    "first_response_at",
    "resolved_at",
    "category",
    "priority",
    "queue",
    "assigned_agent",
    "status",
    "channel",
    "reassignment_count",
    "customer_id",
)

LOWERCASE_COLUMNS: frozenset[str] = frozenset({"category", "status", "channel", "priority"})


class CSVParseError(ValueError):
    """Structured parse error translated to HTTP 422 by the ingestion API."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ParsedCSV:
    rows: list[dict[str, str]]
    extra_columns: list[str]


def parse_csv_bytes(raw_bytes: bytes, filename: str) -> ParsedCSV:
    """Validate file constraints, decode UTF-8/BOM, verify columns, and normalise cells."""
    clean_filename = Path(filename or "").name
    if Path(clean_filename).suffix.lower() != ".csv":
        raise CSVParseError(
            "Only .csv files are accepted. Please upload a file with a .csv extension."
        )

    if len(raw_bytes) == 0:
        raise CSVParseError("The uploaded CSV file is empty.")

    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise CSVParseError(
            f"The uploaded file exceeds the 10 MB size limit ({len(raw_bytes):,} bytes)."
        )

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVParseError(
            "Unable to decode file as UTF-8. Please save the CSV as UTF-8 (UTF-8 with BOM is supported)."
        ) from exc

    if not text.strip():
        raise CSVParseError("The uploaded CSV file contains no header or ticket rows.")

    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            keep_default_na=False,
        )
    except (pd.errors.EmptyDataError, pd.errors.ParserError, csv.Error, ValueError) as exc:
        raise CSVParseError(
            f"Unable to parse CSV structure: {exc}. Ensure the file is a valid comma-separated table with a header row."
        ) from exc

    # Strip whitespace around column header names.
    normalised_headers = [str(col).strip() for col in df.columns]
    if len(set(normalised_headers)) != len(normalised_headers):
        raise CSVParseError("CSV header contains duplicate column names.")
    df.columns = normalised_headers

    required_set = set(REQUIRED_COLUMNS)
    present_set = set(normalised_headers)
    missing = [col for col in REQUIRED_COLUMNS if col not in present_set]
    unexpected = [col for col in normalised_headers if col not in required_set]

    if missing:
        parts = [f"Missing required column(s): {', '.join(missing)}."]
        if unexpected:
            parts.append(f"Unexpected column(s): {', '.join(unexpected)}.")
        raise CSVParseError(
            " ".join(parts),
            details={
                "missing_columns": missing,
                "unexpected_columns": unexpected,
                "required_columns": list(REQUIRED_COLUMNS),
            },
        )

    if len(df) == 0:
        raise CSVParseError("The uploaded CSV has a valid header row but contains 0 ticket rows.")

    if len(df) > MAX_ROWS:
        raise CSVParseError(
            f"CSV contains {len(df):,} rows, exceeding the maximum limit of {MAX_ROWS:,} rows."
        )

    # Ignore extra columns and keep only required columns in canonical order.
    df = df.loc[:, list(REQUIRED_COLUMNS)].copy()

    # Normalise every cell as plain text (never interpret formula prefixes = + - @).
    for col in REQUIRED_COLUMNS:
        series = df[col].astype(str).str.strip()
        if col in LOWERCASE_COLUMNS:
            series = series.str.lower()
        df[col] = series

    rows = df.to_dict(orient="records")
    return ParsedCSV(rows=rows, extra_columns=unexpected)
