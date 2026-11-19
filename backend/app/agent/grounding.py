"""Deterministic grounding and causal-wording verification for agent answer blocks."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.prompts import BANNED_CAUSAL_PHRASES
from app.agent.tools import ToolResult

BlockType = Literal[
    "finding",
    "hypothesis",
    "recommended_next_step",
    "clarifying_question",
    "limitation",
]

MAX_BLOCKS = 8
MAX_BLOCK_TEXT_CHARS = 600

# Units that make even small integers (0-10) meaningful operational figures.
_UNIT_PATTERN = (
    r"(?:%|percent\b|hours?\b|hrs?\b|h\b|tickets?\b|days?\b|categor(?:y|ies)\b|agents?\b)"
)

# Pre-strip dates, ISO timestamps, clock times, and alphanumeric identifiers.
_ISO_DATETIME_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?\b"
)
_SLASH_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_MONTH_NAME = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_WRITTEN_DATE_RE = re.compile(
    rf"\b(?:{_MONTH_NAME}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}\s+{_MONTH_NAME}(?:\s+\d{{4}})?)\b",
    re.IGNORECASE,
)
_CLOCK_RANGE_RE = re.compile(r"\b\d{1,2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2})?\b")
_AGENT_OR_STAGE_ID_RE = re.compile(r"\b(?:Agent|Stage|Step)\s+\d+\b", re.IGNORECASE)
_CALL_OR_FINDING_ID_RE = re.compile(r"\b(?:[A-Za-z]{1,4}-\d+|c\d+|p\d{2})\b")

# Match signed/comma-formatted numbers not glued to letters, plus optional trailing unit.
_NUMBER_RE = re.compile(
    rf"(?<![A-Za-z0-9_.])(-?\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    rf"(?:\s*({_UNIT_PATTERN}))?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)

_CAUSAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (phrase, re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE))
    for phrase in BANNED_CAUSAL_PHRASES
)


class AnswerBlock(BaseModel):
    """One structured output block from the investigation agent."""

    model_config = ConfigDict(extra="forbid")

    type: BlockType
    text: str = Field(min_length=1, max_length=MAX_BLOCK_TEXT_CHARS)
    evidence_call_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Block text must not be empty.")
        return cleaned

    @field_validator("evidence_call_ids")
    @classmethod
    def _clean_call_ids(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            cid = item.strip()
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out


class StructuredAnswer(BaseModel):
    """Top-level JSON answer contract returned by the investigation agent."""

    model_config = ConfigDict(extra="forbid")

    blocks: list[AnswerBlock] = Field(min_length=1, max_length=MAX_BLOCKS)


class GroundingWarning(BaseModel):
    """Non-destructive warning attached to a specific answer block."""

    model_config = ConfigDict(extra="forbid")

    block_index: int
    code: Literal[
        "ungrounded_number",
        "number_only_in_uncited_call",
        "unsupported_finding",
        "causal_wording_in_finding",
    ]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


def _collect_numeric_values(obj: Any, acc: list[float]) -> None:
    """Recursively collect every non-boolean numeric value from tool output data."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
        return
    if isinstance(obj, list):
        for item in obj:
            _collect_numeric_values(item, acc)
        return
    if isinstance(obj, dict):
        for val in obj.values():
            _collect_numeric_values(val, acc)


def _extract_tool_numbers(result: ToolResult) -> list[float]:
    nums: list[float] = []
    if not result.ok:
        return nums
    _collect_numeric_values(result.data, nums)
    if result.original_row_count is not None:
        nums.append(float(result.original_row_count))
    return nums


def _extract_candidate_numbers(text: str) -> list[tuple[str, float, int, bool]]:
    """Return (raw_display, numeric_value, decimal_places, is_percent) from block text."""
    sanitized = _ISO_DATETIME_RE.sub(" ", text)
    sanitized = _SLASH_DATE_RE.sub(" ", sanitized)
    sanitized = _WRITTEN_DATE_RE.sub(" ", sanitized)
    sanitized = _CLOCK_RANGE_RE.sub(" ", sanitized)
    sanitized = _AGENT_OR_STAGE_ID_RE.sub(" ", sanitized)
    sanitized = _CALL_OR_FINDING_ID_RE.sub(" ", sanitized)

    extracted: list[tuple[str, float, int, bool]] = []
    for match in _NUMBER_RE.finditer(sanitized):
        raw_num = match.group(1)
        unit = (match.group(2) or "").strip().lower()
        normalized = raw_num.replace(",", "")
        has_decimal = "." in normalized
        decimals = len(normalized.split(".")[1]) if has_decimal else 0
        try:
            value = float(normalized)
        except ValueError:
            continue

        # Ignore standalone 4-digit years unless accompanied by an operational unit.
        if not has_decimal and not unit and 1900 <= value <= 2099:
            continue

        # Ignore small integers 0-10 when they have no operational unit.
        if not has_decimal and not unit and 0 <= value <= 10:
            continue

        is_percent = unit in ("%", "percent")
        display = f"{raw_num}%" if unit == "%" else (f"{raw_num} {unit}" if unit else raw_num)
        extracted.append((display, value, decimals, is_percent))

    return extracted


def _matches_any_value(
    shown_value: float,
    decimals: int,
    is_percent: bool,
    pool: list[float],
) -> bool:
    """Return True if shown_value matches any pool value at the shown precision."""
    half_step = 0.5 * (10.0 ** (-decimals)) + 1e-9
    for candidate in pool:
        if abs(candidate - shown_value) <= half_step:
            return True
        if is_percent and abs((candidate * 100.0) - shown_value) <= half_step:
            return True
        # Also allow comparing absolute magnitude when text uses phrasing like "0.56 h lower"
        if shown_value >= 0 and candidate < 0 and abs(abs(candidate) - shown_value) <= half_step:
            return True
    return False


def check_grounding(
    blocks: list[AnswerBlock],
    tool_trace: list[ToolResult],
) -> list[GroundingWarning]:
    """Deterministically check every block for numeric grounding, citations, and causal wording.

    Warnings are returned without modifying or removing any block content.
    """
    warnings: list[GroundingWarning] = []

    trace_by_id: dict[str, ToolResult] = {r.call_id: r for r in tool_trace}
    numbers_by_call: dict[str, list[float]] = {
        r.call_id: _extract_tool_numbers(r) for r in tool_trace if r.ok
    }

    for idx, block in enumerate(blocks):
        cited_ids = list(block.evidence_call_ids)
        valid_cited_ids = [
            cid for cid in cited_ids if cid in trace_by_id and trace_by_id[cid].ok
        ]
        invalid_cited_ids = [
            cid for cid in cited_ids if cid not in trace_by_id or not trace_by_id[cid].ok
        ]

        # 1. Finding citation requirement
        if block.type == "finding":
            if not cited_ids:
                warnings.append(
                    GroundingWarning(
                        block_index=idx,
                        code="unsupported_finding",
                        message="This finding does not cite any supporting tool call.",
                        details={"cited_call_ids": []},
                    )
                )
            elif invalid_cited_ids:
                warnings.append(
                    GroundingWarning(
                        block_index=idx,
                        code="unsupported_finding",
                        message=(
                            "This finding cites a missing or failed tool call: "
                            + ", ".join(invalid_cited_ids)
                            + "."
                        ),
                        details={
                            "cited_call_ids": cited_ids,
                            "invalid_call_ids": invalid_cited_ids,
                        },
                    )
                )

            # 2. Causal wording check on findings only
            for phrase, pattern in _CAUSAL_PATTERNS:
                if pattern.search(block.text):
                    warnings.append(
                        GroundingWarning(
                            block_index=idx,
                            code="causal_wording_in_finding",
                            message=(
                                f"Finding uses causal wording ('{phrase}'). "
                                "Findings should state observed patterns without claiming causation."
                            ),
                            details={"phrase": phrase},
                        )
                    )
                    break

        # 3. Numeric grounding check
        candidates = _extract_candidate_numbers(block.text)
        if not candidates:
            continue

        cited_pool: list[float] = []
        for cid in valid_cited_ids:
            cited_pool.extend(numbers_by_call.get(cid, []))

        for display, value, decimals, is_percent in candidates:
            if cited_pool and _matches_any_value(value, decimals, is_percent, cited_pool):
                continue

            # Check whether the number exists in any uncited successful tool call
            uncited_matches = [
                cid
                for cid, nums in numbers_by_call.items()
                if cid not in valid_cited_ids
                and _matches_any_value(value, decimals, is_percent, nums)
            ]
            if uncited_matches:
                warnings.append(
                    GroundingWarning(
                        block_index=idx,
                        code="number_only_in_uncited_call",
                        message=(
                            f"Figure '{display}' was not found in cited calls "
                            f"({', '.join(valid_cited_ids) or 'none'}), "
                            f"but appears in uncited call(s): {', '.join(uncited_matches)}."
                        ),
                        details={
                            "number": display,
                            "cited_call_ids": valid_cited_ids,
                            "found_in_call_ids": uncited_matches,
                        },
                    )
                )
            else:
                warnings.append(
                    GroundingWarning(
                        block_index=idx,
                        code="ungrounded_number",
                        message=(
                            f"Figure '{display}' could not be verified against cited tool outputs "
                            f"({', '.join(valid_cited_ids) or 'no tool calls cited'})."
                        ),
                        details={
                            "number": display,
                            "checked_call_ids": valid_cited_ids,
                        },
                    )
                )

    return warnings
