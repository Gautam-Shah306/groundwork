"""Deterministic rule-based findings generator from computed MetricResult objects."""

from __future__ import annotations

from app.findings.models import (
    EvidenceRef,
    Finding,
    FindingStrength,
    FindingText,
    ValidationQuestion,
)
from app.metrics.config import MetricsConfig
from app.metrics.results import MetricResult

STRENGTH_ORDER: dict[str | None, int] = {
    "strong": 0,
    "moderate": 1,
    "weak": 2,
    "info": 3,
    None: 4,
}

GENERAL_VALIDATION_QUESTIONS: tuple[ValidationQuestion, ...] = (
    ValidationQuestion(
        text="Confirm the client's agreed first-response and resolution SLA targets; current thresholds are illustrative configuration defaults.",
        kind="template_question",
        finding_id=None,
    ),
    ValidationQuestion(
        text="Confirm actual support team shift hours, handoff rules, and whether overnight queue waiting is expected operating policy.",
        kind="template_question",
        finding_id=None,
    ),
    ValidationQuestion(
        text="Confirm what the ticket status field represents at extraction time (live queue snapshot versus period-end state).",
        kind="template_question",
        finding_id=None,
    ),
)


def _insufficient_finding(
    *,
    finding_id: str,
    title: str,
    evidence: list[EvidenceRef],
    hypothesis_text: str,
    limitation_text: str,
    question_text: str,
) -> Finding:
    return Finding(
        id=finding_id,
        title=title,
        strength=None,
        status="insufficient_data",
        observation=FindingText(
            type="observed_fact",
            text="Not enough data to assess this pattern against the minimum sample threshold.",
        ),
        hypothesis=FindingText(type="hypothesis", text=hypothesis_text),
        evidence=evidence,
        limitations=[limitation_text],
        validation_questions=[
            ValidationQuestion(
                text=question_text,
                kind="template_question",
                finding_id=finding_id,
            )
        ],
    )


def _build_triage_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding | None:
    metric = results["triage_share_of_first_response"]
    triage_metric = results["triage_time"]
    n = int(metric.data["n"])
    share = metric.data["share"]
    thresholds = config.findings_thresholds.triage_share

    evidence = [
        EvidenceRef(
            metric_id="triage_share_of_first_response",
            params=dict(metric.params),
            label="Triage share of first-response time",
            value=share,
            unit="ratio",
            n=n,
        ),
        EvidenceRef(
            metric_id="triage_time",
            params=dict(triage_metric.params),
            label="Median time to assignment",
            value=triage_metric.data["median"],
            unit="hours",
            n=int(triage_metric.data["n"]),
        ),
    ]

    if n < config.min_sample or share is None:
        return _insufficient_finding(
            finding_id="F-TRIAGE",
            title="Time to assignment share of first-response time",
            evidence=evidence,
            hypothesis_text="Manual intake sorting might represent a meaningful portion of response waits, though more records are needed to assess.",
            limitation_text=f"Sample size (n={n}) is below the configured minimum of {config.min_sample}.",
            question_text="Who assigns incoming tickets from the shared inbox, and at what cadence?",
        )

    if share < thresholds.weak:
        return None

    strength: FindingStrength
    if share >= thresholds.strong:
        strength = "strong"
    elif share >= thresholds.moderate:
        strength = "moderate"
    else:
        strength = "weak"

    pct = share * 100.0
    median_triage = triage_metric.data["median"]
    median_phrase = (
        f" and median time to assignment is {median_triage:.2f} hours"
        if median_triage is not None
        else ""
    )

    return Finding(
        id="F-TRIAGE",
        title="Time to assignment accounts for a large share of first-response time",
        strength=strength,
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"Across {n} tickets with valid triage and response timestamps, "
                f"time before assignment represents {pct:.1f}% of aggregate first-response time"
                f"{median_phrase}."
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                "Manual triage in a shared intake queue may be delaying initial assignment "
                "before specialists begin handling customer requests."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Aggregate triage share includes overnight waiting outside staffed hours (09:00-22:00 IST).",
            "Unanswered tickets are excluded from first-response time calculations (right-censoring).",
        ],
        validation_questions=[
            ValidationQuestion(
                text="Who assigns incoming tickets from the shared inbox, and when does triage occur during each shift?",
                kind="template_question",
                finding_id="F-TRIAGE",
            )
        ],
    )


def _build_misroute_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding | None:
    metric = results["reassignment_rate"]
    overall = metric.data["overall"]
    by_category: list[dict] = metric.data["by_category"]
    thresholds = config.findings_thresholds.misrouting

    if overall["n"] < config.min_sample or not by_category:
        return _insufficient_finding(
            finding_id="F-MISROUTE",
            title="Category reassignment concentration",
            evidence=[
                EvidenceRef(
                    metric_id="reassignment_rate",
                    params=dict(metric.params),
                    label="Overall reassignment rate",
                    value=overall["rate"],
                    unit="ratio",
                    n=int(overall["n"]),
                )
            ],
            hypothesis_text="Certain categories could be routed inconsistently between queues, though sample size is currently too small.",
            limitation_text=f"Usable ticket count (n={overall['n']}) is below the minimum sample of {config.min_sample}.",
            question_text="Do queue ownership boundaries overlap between Order support and Returns and refunds?",
        )

    candidates = [
        row
        for row in by_category
        if row["n"] >= thresholds.min_category_n and row["rate"] >= thresholds.min_rate
    ]
    if not candidates:
        return None

    candidate_names = {row["category"] for row in candidates}
    baseline_rows = [row for row in by_category if row["category"] not in candidate_names]
    if not baseline_rows:
        return None

    baseline_n = sum(int(r["n"]) for r in baseline_rows)
    baseline_reassigned = sum(int(r["reassigned_count"]) for r in baseline_rows)
    if baseline_n == 0:
        return None
    baseline_rate = baseline_reassigned / baseline_n

    flagged: list[tuple[dict, float]] = []
    for row in candidates:
        ratio = (row["rate"] / baseline_rate) if baseline_rate > 0 else float("inf")
        if ratio >= thresholds.ratio_moderate:
            flagged.append((row, ratio))

    if not flagged:
        return None

    max_ratio = max(ratio for _, ratio in flagged)
    strength: FindingStrength = (
        "strong" if max_ratio >= thresholds.ratio_strong else "moderate"
    )

    flagged_names = [row["category"] for row, _ in flagged]
    flagged_rates_text = ", ".join(
        f"{row['category']} ({row['rate'] * 100.0:.1f}%, n={row['n']})"
        for row, _ in flagged
    )

    evidence = [
        EvidenceRef(
            metric_id="reassignment_rate",
            params={"category": row["category"]},
            label=f"Reassignment rate ({row['category']})",
            value=row["rate"],
            unit="ratio",
            n=int(row["n"]),
        )
        for row, _ in flagged
    ]
    evidence.append(
        EvidenceRef(
            metric_id="reassignment_rate",
            params=dict(metric.params),
            label="Overall reassignment rate",
            value=overall["rate"],
            unit="ratio",
            n=int(overall["n"]),
        )
    )

    return Finding(
        id="F-MISROUTE",
        title="Elevated reassignment rates concentrated in specific ticket categories",
        strength=strength,
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"Reassignment rates are higher in {flagged_rates_text} compared with "
                f"{baseline_rate * 100.0:.1f}% across the remaining categories combined "
                f"(n={baseline_n})."
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                f"Initial intake routing for {', '.join(flagged_names)} may overlap with "
                "adjacent queues, or agents might transfer ambiguous cases for specialist handling."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Reassignment counts do not distinguish misrouting errors from intentional specialist escalations.",
            "Category labels reflect final stored categories rather than initial intake labels.",
        ],
        validation_questions=[
            ValidationQuestion(
                text="Do Order support and Returns and refunds overlap in scope for delivery-related or refund-adjacent tickets?",
                kind="template_question",
                finding_id="F-MISROUTE",
            )
        ],
    )


def _build_evening_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding | None:
    metric = results["first_response_by_band"]
    bands = {row["band"]: row for row in metric.data}
    evening = bands.get("evening", {"n": 0, "median": None})
    afternoon = bands.get("afternoon", {"n": 0, "median": None})
    thresholds = config.findings_thresholds.evening

    evidence = [
        EvidenceRef(
            metric_id="first_response_by_band",
            params={"band": "evening"},
            label="Evening band median first-response time",
            value=evening["median"],
            unit="hours",
            n=int(evening["n"]),
        ),
        EvidenceRef(
            metric_id="first_response_by_band",
            params={"band": "afternoon"},
            label="Afternoon band median first-response time",
            value=afternoon["median"],
            unit="hours",
            n=int(afternoon["n"]),
        ),
    ]

    if (
        int(evening["n"]) < config.min_sample
        or int(afternoon["n"]) < config.min_sample
        or evening["median"] is None
        or afternoon["median"] is None
    ):
        return _insufficient_finding(
            finding_id="F-EVENING",
            title="Evening versus afternoon first-response gap",
            evidence=evidence,
            hypothesis_text="Evening shift coverage might differ from afternoon capacity, though more records are needed in both bands.",
            limitation_text=(
                f"Evening (n={evening['n']}) or afternoon (n={afternoon['n']}) sample is below "
                f"the minimum sample of {config.min_sample}."
            ),
            question_text="How many agents are scheduled during the 18:00-22:00 IST window compared with 14:00-18:00 IST?",
        )

    diff_hours = float(evening["median"] - afternoon["median"])
    if diff_hours < thresholds.diff_hours_moderate:
        return None

    strength: FindingStrength = (
        "strong" if diff_hours >= thresholds.diff_hours_strong else "moderate"
    )

    return Finding(
        id="F-EVENING",
        title="Longer first-response waits for evening-created tickets",
        strength=strength,
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"Tickets created in the evening band (18:00-22:00 IST, n={evening['n']}) "
                f"show a median first-response time of {evening['median']:.2f} hours versus "
                f"{afternoon['median']:.2f} hours in the afternoon band (14:00-18:00 IST, "
                f"n={afternoon['n']}), a difference of {diff_hours:.2f} hours."
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                "Thinner evening staffing coverage or late-day ticket handovers into the "
                "unstaffed overnight window could contribute to longer waits."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Creation-band comparisons can be confounded by category mix and spillover past the 22:00 IST shift end.",
            "Unanswered tickets are excluded from median first-response times (right-censoring).",
        ],
        validation_questions=[
            ValidationQuestion(
                text="What is the active staffing headcount during 18:00-22:00 IST compared with the 14:00-18:00 IST shift overlap?",
                kind="template_question",
                finding_id="F-EVENING",
            )
        ],
    )


def _build_workload_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding | None:
    workload = results["agent_workload"]
    factors = results["factor_comparison"]
    thresholds = config.findings_thresholds.workload

    top_n = int(workload.data["top_n"])
    top_share = workload.data["top_n_share"]
    assigned_total = int(workload.data["assigned_total"])

    factor_row = next(
        (r for r in factors.data if r["factor_id"] == "top_n_agents_vs_others"),
        None,
    )
    top_n_resp = int(factor_row["group_a_n"]) if factor_row else 0
    other_n_resp = int(factor_row["group_b_n"]) if factor_row else 0
    diff_hours = factor_row["difference_hours"] if factor_row else None

    evidence = [
        EvidenceRef(
            metric_id="agent_workload",
            params={"top_n": top_n},
            label=f"Top-{top_n} agents share of assigned volume",
            value=top_share,
            unit="ratio",
            n=assigned_total,
        ),
        EvidenceRef(
            metric_id="factor_comparison",
            params={"factor_id": "top_n_agents_vs_others"},
            label=f"Median FRT difference (top-{top_n} vs other agents)",
            value=diff_hours,
            unit="hours",
            n=top_n_resp + other_n_resp,
        ),
    ]

    if (
        top_n_resp < config.min_sample
        or other_n_resp < config.min_sample
        or top_share is None
        or diff_hours is None
    ):
        return _insufficient_finding(
            finding_id="F-WORKLOAD",
            title=f"Workload concentration across top-{top_n} agents",
            evidence=evidence,
            hypothesis_text="Uneven ticket allocation across agents might affect turnaround times, though more observations per group are needed.",
            limitation_text=(
                f"Top-{top_n} group (n={top_n_resp}) or comparison group (n={other_n_resp}) "
                f"is below the minimum sample of {config.min_sample}."
            ),
            question_text="Are tickets allocated evenly across shifts, or do senior specialists intentionally take higher volume?",
        )

    abs_diff = abs(float(diff_hours))
    if abs_diff >= thresholds.frt_diff_hours_strong:
        strength: FindingStrength = "strong"
    elif abs_diff >= thresholds.frt_diff_hours_moderate:
        strength = "moderate"
    else:
        strength = "weak"

    return Finding(
        id="F-WORKLOAD",
        title=f"Top-{top_n} agents handle a concentrated share of assigned volume",
        strength=strength,
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"The top {top_n} agents account for {top_share * 100.0:.1f}% of assigned "
                f"tickets (n={assigned_total}), with a {diff_hours:.2f}-hour difference in "
                f"median first-response time compared with other agents' tickets."
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                "Differences in shift schedules, tenure, or manual queue cherry-picking "
                "may explain uneven ticket counts across agents."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Observed group differences are confounded by shift assignment (day versus late shift) and ticket complexity.",
            "Assigned-agent counts do not measure hours worked or time spent coaching teammates.",
        ],
        validation_questions=[
            ValidationQuestion(
                text="Do the highest-volume agents work longer shifts or handle simpler queues compared with other agents?",
                kind="template_question",
                finding_id="F-WORKLOAD",
            )
        ],
    )


def _build_backlog_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding | None:
    metric = results["backlog_ageing"]
    total_backlog = int(metric.data["total_open_backlog"])
    buckets = {b["bucket"]: b for b in metric.data["buckets"]}
    over_7d = buckets.get("gte_7d", {"count": 0, "share": 0.0})
    over_7d_count = int(over_7d["count"])
    over_7d_share = float(over_7d["share"])
    oldest_days = metric.data["oldest_age_days"]
    thresholds = config.findings_thresholds.backlog

    evidence = [
        EvidenceRef(
            metric_id="backlog_ageing",
            params={"bucket": "gte_7d"},
            label="Open/pending tickets aged >= 7 days",
            value=over_7d_count,
            unit="tickets",
            n=total_backlog,
        ),
        EvidenceRef(
            metric_id="backlog_ageing",
            params={"bucket": "gte_7d", "field": "share"},
            label="Share of open backlog aged >= 7 days",
            value=over_7d_share,
            unit="ratio",
            n=total_backlog,
        ),
    ]

    if total_backlog < config.min_sample:
        return _insufficient_finding(
            finding_id="F-BACKLOG",
            title="Ageing unresolved backlog",
            evidence=evidence,
            hypothesis_text="Stale open tickets might be accumulating without follow-up, though the open backlog sample is below threshold.",
            limitation_text=(
                f"Open/pending backlog count (n={total_backlog}) is below the minimum sample of {config.min_sample}."
            ),
            question_text="Are pending tickets awaiting customer replies or internal warehouse action?",
        )

    if over_7d_share < thresholds.min_share_over_7d:
        return None

    if over_7d_share >= 0.5:
        strength: FindingStrength = "moderate"
    elif over_7d_count > 0:
        strength = "weak"
    else:
        strength = "info"

    oldest_text = (
        f" The oldest open ticket is {oldest_days:.1f} days old at period end."
        if oldest_days is not None
        else ""
    )

    return Finding(
        id="F-BACKLOG",
        title="Unresolved tickets aged more than 7 days in backlog",
        strength=strength,
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"At dataset period end, {over_7d_count} of {total_backlog} open or pending "
                f"tickets ({over_7d_share * 100.0:.1f}%) are 7 days old or older.{oldest_text}"
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                "Stalled pending threads or unmonitored reassignments could be leaving older "
                "tickets unresolved without automatic escalation."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Ticket status reflects an extraction-time snapshot rather than historical daily backlog trajectories.",
            "Pending tickets may be waiting on customer photos or courier confirmations rather than agent action.",
        ],
        validation_questions=[
            ValidationQuestion(
                text="How are pending tickets aged over 7 days reviewed or auto-closed when customers stop replying?",
                kind="template_question",
                finding_id="F-BACKLOG",
            )
        ],
    )


def _build_coverage_finding(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> Finding:
    frt = results["first_response_time"]
    res = results["resolution_time"]
    triage = results["triage_time"]
    vol = results["volume_by_category"]

    total_rows = vol.n_included + vol.n_excluded
    excluded_all = vol.n_excluded
    excluded_resp = frt.n_excluded
    excluded_res = res.n_excluded
    excluded_triage = triage.n_excluded

    all_reasons: dict[str, int] = {}
    for metric in (vol, frt, res, triage):
        for code, count in metric.exclusions.items():
            all_reasons[code] = max(all_reasons.get(code, 0), count)

    reason_text = (
        ", ".join(f"{code} ({cnt})" for code, cnt in sorted(all_reasons.items()))
        if all_reasons
        else "none"
    )

    evidence = [
        EvidenceRef(
            metric_id="first_response_time",
            params={"field": "n_excluded"},
            label="Rows excluded from response metrics",
            value=excluded_resp,
            unit="rows",
            n=total_rows,
        ),
        EvidenceRef(
            metric_id="resolution_time",
            params={"field": "n_excluded"},
            label="Rows excluded from resolution metrics",
            value=excluded_res,
            unit="rows",
            n=total_rows,
        ),
        EvidenceRef(
            metric_id="triage_time",
            params={"field": "n_excluded"},
            label="Rows excluded from triage metrics",
            value=excluded_triage,
            unit="rows",
            n=total_rows,
        ),
    ]

    return Finding(
        id="F-COVERAGE",
        title="Data quality exclusions across metric scopes",
        strength="info",
        status="supported",
        observation=FindingText(
            type="observed_fact",
            text=(
                f"Out of {total_rows} stored rows, {excluded_all} are excluded from all metrics, "
                f"{excluded_resp} from response metrics, {excluded_res} from resolution metrics, "
                f"and {excluded_triage} from triage metrics. Flagged reasons: {reason_text}."
            ),
        ),
        hypothesis=FindingText(
            type="hypothesis",
            text=(
                "Export formatting gaps, duplicate rows, or timestamp clock discrepancies in "
                "the source helpdesk may explain the flagged records."
            ),
        ),
        evidence=evidence,
        limitations=[
            "Excluded records are retained in storage for inspection; if exclusions cluster in one queue or shift, metrics could be biased."
        ],
        validation_questions=[
            ValidationQuestion(
                text="Are the flagged missing timestamps and unknown categories expected artifacts of the helpdesk CSV export?",
                kind="template_question",
                finding_id="F-COVERAGE",
            )
        ],
    )


def generate_findings(
    results: dict[str, MetricResult],
    config: MetricsConfig,
) -> list[Finding]:
    """Generate ordered deterministic rule-based findings from computed metrics."""
    raw_findings: list[Finding | None] = [
        _build_triage_finding(results, config),
        _build_misroute_finding(results, config),
        _build_evening_finding(results, config),
        _build_workload_finding(results, config),
        _build_backlog_finding(results, config),
        _build_coverage_finding(results, config),
    ]

    findings = [f for f in raw_findings if f is not None]
    findings.sort(key=lambda f: (STRENGTH_ORDER.get(f.strength, 99), f.id))
    return findings


def combine_validation_questions(findings: list[Finding]) -> list[ValidationQuestion]:
    """Combine per-finding template questions with general validation questions."""
    combined: list[ValidationQuestion] = []
    seen: set[str] = set()
    for finding in findings:
        for question in finding.validation_questions:
            if question.text not in seen:
                seen.add(question.text)
                combined.append(question)
    for general in GENERAL_VALIDATION_QUESTIONS:
        if general.text not in seen:
            seen.add(general.text)
            combined.append(general)
    return combined
