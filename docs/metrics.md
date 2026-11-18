# Groundwork — Deterministic Metrics & Findings Specification

All business metrics and diagnostic findings in Groundwork are computed deterministically by pure Python functions under `backend/app/metrics/` and `backend/app/findings/` (`R1`, `R4`). All configuration defaults live in [`config/metrics.yaml`](../config/metrics.yaml) and are validated with Pydantic.

---

## Global Conventions

- **As-of rule (`as_of`):** Every age- and threshold-based metric (backlog ageing, unanswered/unresolved tickets past SLA) is anchored to the dataset's **`period_end`** timestamp — never wall-clock `now()`. This guarantees reproducible outputs whenever a dataset is re-opened.
- **Timezone rule:** Stored timestamps are UTC. Calendar dates (`volume_by_day`), hour-of-day (`volume_by_hour`), and creation-hour bands (`volume_by_band`, `first_response_by_band`) are evaluated in **`Asia/Kolkata` (`+05:30` IST)**. A ticket created at `19:00 UTC` belongs to the next IST calendar date (`00:30 IST`).
- **Percentile method:** `numpy.percentile(..., method="linear")` (`50` = median, `90` = p90). Empty samples return `n = 0` with `null` summary values and never raise.
- **Validation scopes & non-dropping rule:** Invalid rows are stored in full and never silently dropped. Every `MetricResult` reports `n_included`, `n_excluded`, and `exclusions` (`flag_code -> count`):
  - `all`: excludes rows carrying any flag affecting `all_metrics`.
  - `response`: excludes rows carrying any flag affecting `all_metrics` or `response_metrics`.
  - `resolution`: excludes rows carrying any flag affecting `all_metrics` or `resolution_metrics`.
  - `triage`: excludes rows carrying any flag affecting `all_metrics` or `triage_metrics`.
  - `response+triage`: excludes rows carrying any flag affecting `all_metrics`, `response_metrics`, or `triage_metrics`.
- **Right-censoring caveat:** Unanswered tickets (missing `first_response_at` on open/pending rows) are excluded from first-response time distributions and reported separately as `unanswered_count`. Unresolved tickets (open/pending) are excluded from resolution time distributions and reported separately as `unresolved_count`.
- **Rounding rule:** Internal calculations preserve full floating-point precision; the diagnostics API rounds floats to 2 decimal places only at serialization time.

### Creation Bands (`Asia/Kolkata`, `[start, end)`)
| Band | IST Hours | Notes |
|---|---|---|
| `morning` | `09:00–14:00` | Day shift |
| `afternoon` | `14:00–18:00` | Day + late shift overlap |
| `evening` | `18:00–22:00` | Late shift only |
| `overnight` | `22:00–09:00` | Wraps midnight; unstaffed |

### Backlog Ageing Buckets (Days as of `as_of`, `[min, max)`)
- `lt_1d`: `[0, 1)` days
- `d1_3`: `[1, 3)` days
- `d3_7`: `[3, 7)` days
- `gte_7d`: `[7, ∞)` days

### Key Formula Definitions
- **Gini coefficient:** For per-agent assigned ticket counts $x_1, \dots, x_n$:
  $$G = \frac{\sum_{i=1}^{n} \sum_{j=1}^{n} |x_i - x_j|}{2 n \sum_{i=1}^{n} x_i}$$
  Equal counts yield $G = 0$; one agent holding all volume among $n$ agents yields $G = (n - 1)/n$.
- **Triage share of first-response time:** Aggregate sum ratio over tickets valid for both `response` and `triage` scopes with `created_at`, `assigned_at`, and `first_response_at`:
  $$\text{Triage share} = \frac{\sum (\text{assigned\_at} - \text{created\_at})}{\sum (\text{first\_response\_at} - \text{created\_at})}$$

---

## Metric Reference

| Metric ID | Title | Definition & Formula | Unit | Input Fields | Scope | Key Limitations |
|---|---|---|---|---|---|---|
| `first_response_time` | First-response time | `describe_hours(first_response_at - created_at)` + separate `unanswered_count` | `hours` | `created_at`, `first_response_at` | `response` | Right-censored (unanswered excluded); includes overnight waiting. |
| `agent_response_time` | Agent response time | `describe_hours(first_response_at - assigned_at)` | `hours` | `assigned_at`, `first_response_at` | `response+triage` | Requires both assignment and first-response timestamps. |
| `triage_time` | Time to assignment (triage lag) | `describe_hours(assigned_at - created_at)` + separate `unassigned_count` | `hours` | `created_at`, `assigned_at` | `triage` | Includes overnight waiting for off-hours tickets. |
| `triage_share_of_first_response` | Triage share of first-response time | `sum(assigned_at - created_at) / sum(first_response_at - created_at)` | `ratio` | `created_at`, `assigned_at`, `first_response_at` | `response+triage` | Aggregate ratio across all hours (including overnight); excludes unanswered tickets. |
| `resolution_time` | Resolution time | `describe_hours(resolved_at - created_at)` for `status == "resolved"` + separate `unresolved_count` | `hours` | `created_at`, `resolved_at`, `status` | `resolution` | Right-censored (open/pending excluded). |
| `volume_by_day` | Daily ticket volume | Counts and shares by `created_at` date in IST | `tickets` | `created_at` | `all` | Depends on complete export over the date range. |
| `volume_by_hour` | Ticket volume by hour of day | Counts and shares across IST hours `0..23` | `tickets` | `created_at` | `all` | Aggregates weekdays and weekends together. |
| `volume_by_band` | Ticket volume by creation band | Counts and shares across configured IST creation bands | `tickets` | `created_at` | `all` | Band boundaries come from `config/metrics.yaml`. |
| `volume_by_category` | Ticket volume by category | Counts and shares grouped by validated `category` | `tickets` | `category` | `all` | Excludes unknown categories flagged under `all_metrics`. |
| `volume_by_channel` | Ticket volume by channel | Counts and shares grouped by `channel` (unknown values bucketed as `unknown`) | `tickets` | `channel` | `all` | Non-standard channel values are grouped into `unknown`. |
| `first_response_by_band` | First-response time by creation band | `describe_hours(first_response_at - created_at)` per IST creation band | `hours` | `created_at`, `first_response_at` | `response` | Overnight includes unstaffed hours; bands may differ in category mix. |
| `category_delay_table` | Category delay and reassignment breakdown | Per category: `n`, median triage, median first response, median resolution, reassignment rate | `mixed` | `category`, timestamps, `status`, `reassignment_count` | `all` (per-column scope) | Each delay column applies its own scope (`triage`, `response`, `resolution`). |
| `backlog_ageing` | Open backlog ageing | Open/pending counts & shares by ageing bucket at `as_of`, category split, and `oldest_age_days` | `tickets` | `status`, `created_at`, `category` | `all` | Extraction-time status snapshot; does not reconstruct historical daily backlog. |
| `agent_workload` | Agent workload distribution | Assigned counts & shares per `assigned_agent`, top-N share, Gini, plus separate `unassigned_count` | `tickets` | `assigned_agent` | `all` | Reflects final assigned agent only; ignores shift length and complexity. |
| `reassignment_rate` | Ticket reassignment rate | Overall, by-category, and by-queue share with `reassignment_count >= 1` and mean count | `ratio` | `reassignment_count`, `category`, `queue` | `all` (+ `reassignment_count_unusable`) | Excludes blank or non-integer `reassignment_count` as `reassignment_count_unusable`. |
| `reassigned_vs_not` | First-response time: reassigned vs not | `describe_hours` of FRT for `reassignment_count >= 1` vs `0` and median difference | `hours` | `created_at`, `first_response_at`, `reassignment_count` | `response` (+ `reassignment_count_unusable`) | Observational association only; not a causal estimate. |
| `sla_attainment` | SLA attainment (illustrative thresholds) | Share of responded tickets `<= 4h` and resolved tickets `<= 72h`, plus counts of unanswered/unresolved past threshold at `as_of` | `ratio` | `created_at`, `first_response_at`, `resolved_at`, `status` | `response` / `resolution` | **Illustrative thresholds from configuration, not agreed with the client.** |
| `factor_comparison` | Factor comparison (observed associations) | Side-by-side medians, `n`, and hour differences for reassigned vs not, evening vs afternoon, top-3 vs other agents, plus median triage lag | `hours` | `created_at`, `assigned_at`, `first_response_at`, `assigned_agent`, `reassignment_count` | `response` / `triage` | Observed associations only; groups overlap and differences are not additive or causal. |

---

## Rule-Based Findings & Thresholds (`backend/app/findings/rules.py`)

Findings are generated strictly from computed `MetricResult` values using template wording. Every finding separates an **Observed fact** (non-causal wording only) from a hedged **Hypothesis** (`may`, `might`, `could`, or `possible`), cites exact `EvidenceRef` metric values, states limitations, and attaches template validation questions.

- **Minimum sample (`min_sample = 30`):** Any finding whose underlying group has `n < 30` is emitted with `status = "insufficient_data"`, `strength = null`, and `"Not enough data to assess"`.
- **Ordering:** `strong` → `moderate` → `weak` → `info` → `insufficient_data`.

| Finding ID | Underlying Metric(s) | Configured Thresholds (`config/metrics.yaml`) |
|---|---|---|
| `F-TRIAGE` | `triage_share_of_first_response`, `triage_time` | `weak >= 0.20`, `moderate >= 0.30`, `strong >= 0.50` |
| `F-MISROUTE` | `reassignment_rate` (`by_category`) | Categories with `n >= 50` and `rate >= 0.20` whose rate is `>= 2.0x` (`moderate`) or `>= 3.0x` (`strong`) the combined rate of remaining categories |
| `F-EVENING` | `first_response_by_band` (`evening` vs `afternoon`) | `evening.median - afternoon.median`: `moderate >= 1.0 h`, `strong >= 2.0 h` |
| `F-WORKLOAD` | `agent_workload`, `factor_comparison` (`top_n_agents_vs_others`) | `top_n = 3`; strength from `|FRT diff|`: `moderate >= 1.0 h`, `strong >= 2.0 h`, else `weak` |
| `F-BACKLOG` | `backlog_ageing` (`gte_7d`) | Open/pending tickets aged `>= 7` days at `as_of` (`min_share_over_7d = 0.0`) |
| `F-COVERAGE` | Scope exclusions across `all`, `response`, `resolution`, `triage` | Always `strength = "info"`, `min_excluded_share = 0.0`, summarising excluded rows and flag codes |
