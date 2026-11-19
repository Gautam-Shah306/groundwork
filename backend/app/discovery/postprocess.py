"""Deterministic post-processing for AI-generated problem briefs."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.agent.prompts import BANNED_CAUSAL_PHRASES
from app.discovery.prompts import VALID_METRIC_IDS
from app.discovery.schema import BriefSections, Item, KnownFactItem, ProblemStatement

HEDGE_PATTERN = re.compile(r"\b(may|might|could|possibly|perhaps)\b", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")

CAUSAL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(phrase) for phrase in BANNED_CAUSAL_PHRASES) + r")\b",
    re.IGNORECASE,
)

SECTIONS_REQUIRING_QUOTES = (
    "themes",
    "stakeholders",
    "workflow_steps",
    "symptoms",
    "impact",
    "known_facts",
)


from app.text_utils import normalize_text_for_comparison, verify_quote


def _extract_number_tokens(text: str) -> set[str]:
    """Extract all individual number strings from text, normalizing commas."""
    tokens = set()
    for raw in NUMBER_PATTERN.findall(text):
        cleaned = raw.replace(",", "")
        tokens.add(cleaned)
        tokens.add(raw)
        # Also include decimal without point if integer
        if "." in cleaned:
            parts = cleaned.split(".")
            tokens.update(parts)
    return tokens


def postprocess_brief(
    brief: BriefSections,
    *,
    client_statement: str,
    notes_text: str,
    raw_draft: dict[str, Any] | None = None,
) -> tuple[BriefSections, list[dict[str, Any]]]:
    """Execute deterministic checks and attach flags without removing content (except invalid KPIs)."""
    warnings: list[dict[str, Any]] = []

    full_notes_text = f"{client_statement}\n{notes_text}"
    norm_source_text = normalize_text_for_comparison(full_notes_text)
    source_numbers = _extract_number_tokens(full_notes_text)

    # 1. Process standard item sections
    for section_name in (
        "themes",
        "stakeholders",
        "workflow_steps",
        "symptoms",
        "impact",
        "assumptions",
        "unknowns",
    ):
        items: list[Item] = getattr(brief, section_name)
        for item in items:
            _process_generic_item(
                item=item,
                section_name=section_name,
                norm_source_text=norm_source_text,
                source_numbers=source_numbers,
                requires_quote=section_name in SECTIONS_REQUIRING_QUOTES,
                warnings=warnings,
            )

    # 2. Process known_facts
    raw_known_facts = []
    if raw_draft and isinstance(raw_draft.get("known_facts"), list):
        raw_known_facts = raw_draft["known_facts"]

    for idx, item in enumerate(brief.known_facts):
        # Force origin and status
        item.origin = "ai"
        item.status = "ai_draft"
        if not item.id:
            item.id = uuid.uuid4().hex[:8]

        # Check if model originally emitted type=observed_fact
        was_observed = False
        if idx < len(raw_known_facts) and isinstance(raw_known_facts[idx], dict):
            if raw_known_facts[idx].get("type") == "observed_fact":
                was_observed = True
        elif getattr(item, "type", None) == "observed_fact":
            was_observed = True

        if was_observed:
            item.type = "client_statement"
            if "type_downgraded" not in item.flags:
                item.flags.append("type_downgraded")
                warnings.append(
                    {
                        "code": "type_downgraded",
                        "section": "known_facts",
                        "item_id": item.id,
                        "text": item.text,
                        "message": "Model labelled item as observed_fact; forced to client_statement.",
                    }
                )

        _verify_quotes_and_numbers(
            item=item,
            section_name="known_facts",
            norm_source_text=norm_source_text,
            source_numbers=source_numbers,
            requires_quote=True,
            warnings=warnings,
        )

    # 3. Process hypotheses (hedge and causal checks)
    for item in brief.hypotheses:
        _process_generic_item(
            item=item,
            section_name="hypotheses",
            norm_source_text=norm_source_text,
            source_numbers=source_numbers,
            requires_quote=False,
            warnings=warnings,
        )

        # Hedge check
        if not HEDGE_PATTERN.search(item.text):
            if "not_hedged" not in item.flags:
                item.flags.append("not_hedged")
                warnings.append(
                    {
                        "code": "not_hedged",
                        "section": "hypotheses",
                        "item_id": item.id,
                        "text": item.text,
                        "message": "Hypothesis is missing required hedging language (may, might, could, possibly).",
                    }
                )

        # Causal wording check
        if CAUSAL_PATTERN.search(item.text):
            if "causal_wording" not in item.flags:
                item.flags.append("causal_wording")
                warnings.append(
                    {
                        "code": "causal_wording",
                        "section": "hypotheses",
                        "item_id": item.id,
                        "text": item.text,
                        "message": "Hypothesis contains banned causal language.",
                    }
                )

    # 4. Process follow_up_questions
    for q in brief.follow_up_questions:
        if not q.id:
            q.id = uuid.uuid4().hex[:8]
        q.status = "open"

    # 5. Process problem_statement
    ps = brief.problem_statement
    ps.status = "ai_draft"
    if ps.text:
        # Number check on problem statement
        for num in _extract_number_tokens(ps.text):
            if num not in source_numbers and "number_not_in_notes" not in ps.flags:
                ps.flags.append("number_not_in_notes")
                warnings.append(
                    {
                        "code": "number_not_in_notes",
                        "section": "problem_statement",
                        "text": ps.text,
                        "message": f"Number '{num}' in problem statement does not appear in interview notes.",
                    }
                )
                break

        # Causal wording check on problem statement
        if CAUSAL_PATTERN.search(ps.text):
            if "causal_wording" not in ps.flags:
                ps.flags.append("causal_wording")
                warnings.append(
                    {
                        "code": "causal_wording",
                        "section": "problem_statement",
                        "text": ps.text,
                        "message": "Problem statement contains banned causal language.",
                    }
                )

    # 6. Process candidate_kpis (filter out unregistered metric IDs)
    valid_kpis = []
    for kpi in brief.candidate_kpis:
        if not kpi.id:
            kpi.id = uuid.uuid4().hex[:8]
        kpi.status = "ai_draft"
        if kpi.metric_id not in VALID_METRIC_IDS:
            warnings.append(
                {
                    "code": "invalid_kpi_dropped",
                    "section": "candidate_kpis",
                    "metric_id": kpi.metric_id,
                    "message": f"Candidate KPI '{kpi.metric_id}' is not in the metric registry and was dropped.",
                }
            )
        else:
            valid_kpis.append(kpi)
    brief.candidate_kpis = valid_kpis

    return brief, warnings


def _process_generic_item(
    *,
    item: Item,
    section_name: str,
    norm_source_text: str,
    source_numbers: set[str],
    requires_quote: bool,
    warnings: list[dict[str, Any]],
) -> None:
    if not item.id:
        item.id = uuid.uuid4().hex[:8]
    item.origin = "ai"
    item.status = "ai_draft"

    _verify_quotes_and_numbers(
        item=item,
        section_name=section_name,
        norm_source_text=norm_source_text,
        source_numbers=source_numbers,
        requires_quote=requires_quote,
        warnings=warnings,
    )


def _verify_quotes_and_numbers(
    *,
    item: Item,
    section_name: str,
    norm_source_text: str,
    source_numbers: set[str],
    requires_quote: bool,
    warnings: list[dict[str, Any]],
) -> None:
    # Quote check
    quote = (item.source_quote or "").strip()
    if not quote:
        item.quote_verified = None
        if requires_quote:
            if "quote_missing" not in item.flags:
                item.flags.append("quote_missing")
                warnings.append(
                    {
                        "code": "quote_missing",
                        "section": section_name,
                        "item_id": item.id,
                        "text": item.text,
                        "message": f"Item in '{section_name}' is missing a supporting verbatim source quote.",
                    }
                )
    else:
        norm_q = normalize_text_for_comparison(quote)
        norm_q_trimmed = norm_q.strip("\"' ")
        if (norm_q and norm_q in norm_source_text) or (norm_q_trimmed and norm_q_trimmed in norm_source_text):
            item.quote_verified = True
        else:
            item.quote_verified = False
            if "quote_not_found" not in item.flags:
                item.flags.append("quote_not_found")
                warnings.append(
                    {
                        "code": "quote_not_found",
                        "section": section_name,
                        "item_id": item.id,
                        "text": item.text,
                        "source_quote": item.source_quote,
                        "message": f"Source quote '{item.source_quote}' was not found in interview notes.",
                    }
                )

    # Number check
    for num in _extract_number_tokens(item.text):
        if num not in source_numbers:
            if "number_not_in_notes" not in item.flags:
                item.flags.append("number_not_in_notes")
                warnings.append(
                    {
                        "code": "number_not_in_notes",
                        "section": section_name,
                        "item_id": item.id,
                        "text": item.text,
                        "message": f"Number '{num}' does not appear in interview notes.",
                    }
                )
            break
