"""Deterministic grounding tests (Part D, scenarios 11-21)."""

from __future__ import annotations

from app.agent.grounding import AnswerBlock, check_grounding
from app.agent.tools import ToolError, ToolResult


def _ok_call(call_id: str, tool: str, data: dict) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        tool=tool,
        args={},
        ok=True,
        data=data,
        error=None,
        duration_ms=5,
    )


def _failed_call(call_id: str, tool: str) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        tool=tool,
        args={},
        ok=False,
        data=None,
        error=ToolError(code="invalid_arguments", message="bad args"),
        duration_ms=2,
    )


def test_number_present_in_cited_result_is_grounded() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07, "n": 1971}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Median first-response time is 6.07 hours across 1,971 tickets.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert warnings == []


def test_rounded_value_at_shown_precision_is_grounded() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Median first-response time is about 6.1 hours (roughly 6 hours).",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert warnings == []


def test_percentage_of_fraction_is_grounded() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "triage_share_of_first_response", "data": {"share": 0.65}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Time to assignment accounts for 65% of total first-response time.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert warnings == []


def test_number_absent_from_cited_results_is_flagged() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Median first-response time is 9.42 hours.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert len(warnings) == 1
    assert warnings[0].code == "ungrounded_number"
    assert warnings[0].block_index == 0
    assert "9.42" in warnings[0].message
    assert warnings[0].details["checked_call_ids"] == ["c1"]


def test_number_present_only_in_uncited_call_is_flagged() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07}},
        ),
        _ok_call(
            "c2",
            "get_backlog_analysis",
            {"metric_id": "backlog_ageing", "data": {"total_open_backlog": 272}},
        ),
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="There are 272 tickets in the open backlog.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert len(warnings) == 1
    assert warnings[0].code == "number_only_in_uncited_call"
    assert warnings[0].details["found_in_call_ids"] == ["c2"]


def test_small_integers_without_units_are_ignored() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="In 2026 (2026-09-07 to 2026-11-01), 2 patterns stand out, including a 6.07 h median.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert warnings == []

    # Small integer WITH a unit ("4 hours") IS checked and flagged if absent
    unit_blocks = [
        AnswerBlock(
            type="finding",
            text="Median wait is 4 hours.",
            evidence_call_ids=["c1"],
        )
    ]
    unit_warnings = check_grounding(unit_blocks, trace)
    assert any(w.code == "ungrounded_number" for w in unit_warnings)


def test_finding_without_valid_evidence_is_flagged_unsupported() -> None:
    trace = [
        _ok_call("c1", "get_ticket_summary", {"kpis": []}),
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Evening waits are longer than afternoon waits.",
            evidence_call_ids=[],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert any(w.code == "unsupported_finding" for w in warnings)


def test_finding_citing_failed_call_is_flagged_unsupported() -> None:
    trace = [
        _failed_call("c1", "get_response_metrics"),
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Evening waits appear elevated.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert any(w.code == "unsupported_finding" for w in warnings)


def test_causal_wording_in_finding_is_flagged() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "triage_share_of_first_response", "data": {"share": 0.65}},
        )
    ]
    blocks = [
        AnswerBlock(
            type="finding",
            text="Delays are caused by manual triage, which is 65% of first-response time.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert any(w.code == "causal_wording_in_finding" for w in warnings)
    assert any(w.details.get("phrase") == "caused" for w in warnings)


def test_hypothesis_block_may_have_no_evidence() -> None:
    trace = [
        _ok_call("c1", "get_ticket_summary", {"kpis": []}),
    ]
    blocks = [
        AnswerBlock(
            type="hypothesis",
            text="Manual queue routing may contribute to pre-assignment waiting.",
            evidence_call_ids=[],
        ),
        AnswerBlock(
            type="recommended_next_step",
            text="Review queue assignment rules with the support operations lead.",
            evidence_call_ids=[],
        ),
    ]
    warnings = check_grounding(blocks, trace)
    assert warnings == []


def test_warnings_do_not_remove_block_content() -> None:
    trace = [
        _ok_call(
            "c1",
            "get_response_metrics",
            {"metric_id": "first_response_time", "data": {"median": 6.07}},
        )
    ]
    original_text = "Delays are caused by routing and reach 99.9 hours."
    blocks = [
        AnswerBlock(
            type="finding",
            text=original_text,
            evidence_call_ids=[],
        )
    ]
    warnings = check_grounding(blocks, trace)
    assert len(warnings) >= 3  # unsupported_finding, causal_wording, ungrounded_number
    assert len(blocks) == 1
    assert blocks[0].text == original_text


def test_number_inside_string_field_of_cited_result_is_grounded_and_not_in_uncited() -> None:
    # Reproduces 0.4: figure '65.3%' appears in text field of cited get_findings
    trace = [
        _ok_call(
            "c1",
            "get_findings",
            {
                "findings": [
                    {
                        "id": "F-TRIAGE",
                        "text": "Across 1971 tickets with valid triage and response timestamps, time before assignment represents 65.3% of aggregate first-response time and median time to assignment is 3.70 hours.",
                        "value": 0.65,
                    }
                ]
            },
        )
    ]
    # When c1 is cited, 65.3% from the text field is grounded and does not trigger ungrounded_number
    blocks_cited = [
        AnswerBlock(
            type="finding",
            text="Across 1971 tickets with valid timestamps, the period before assignment accounts for 65.3% of the aggregate first-response time.",
            evidence_call_ids=["c1"],
        )
    ]
    warnings_cited = check_grounding(blocks_cited, trace)
    assert not any(w.code == "ungrounded_number" for w in warnings_cited)

    # When c1 is NOT cited, 65.3% from the string field does NOT trigger number_only_in_uncited_call
    blocks_uncited = [
        AnswerBlock(
            type="hypothesis",
            text="Pre-assignment waiting might be around 65.3% of total time.",
            evidence_call_ids=[],
        )
    ]
    warnings_uncited = check_grounding(blocks_uncited, trace)
    assert not any(w.code == "number_only_in_uncited_call" for w in warnings_uncited)


def test_verify_quote_tolerates_trailing_punctuation_on_clause_quotes() -> None:
    """Test that verify_quote matches clauses with trailing punctuation added by models."""
    from app.text_utils import verify_quote

    corpus = (
        "In the morning when the team signs on, the shared queue is already overflowing "
        "with overnight emails, web form submissions, and follow-up messages from shoppers "
        "who say they never heard back."
    )
    # Quote with period added by LLM at the end of the clause
    quote_with_period = (
        "The shared queue is already overflowing with overnight emails, web form submissions, "
        "and follow-up messages from shoppers."
    )
    assert verify_quote(quote_with_period, corpus) is True

    # Quote with smart hyphen and comma
    quote_with_dash = (
        "The shared queue is already overflowing with overnight emails, web form submissions, "
        "and follow‑up messages from shoppers,"
    )
    assert verify_quote(quote_with_dash, corpus) is True


def test_verify_quote_rejects_hallucinated_or_substituted_words() -> None:
    """Test that verify_quote strictly rejects quotes with substituted or altered words."""
    from app.text_utils import verify_quote

    corpus = "experienced specialists now spend much of their day answering internal slack questions"
    # Word 'Senior' substituted for 'experienced'
    hallucinated_quote = "Senior specialists now spend much of their day answering internal slack questions"
    assert verify_quote(hallucinated_quote, corpus) is False
