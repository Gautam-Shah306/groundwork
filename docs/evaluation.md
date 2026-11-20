# Evaluation System

## 1. Purpose
Groundwork includes a built-in evaluation framework to benchmark and verify the Support Triage AI pipeline against a test set of 150 synthetically generated, human-labeled tickets (`data/eval_tickets.json`). The evaluator measures classification accuracy, signal extraction fidelity, deterministic priority assignment, queue routing correctness, and automated draft reply safety flags.

## 2. Scope: What Is and Is Not Evaluated
- **What is evaluated:**
  1. **Primary category classification:** Comparison of predicted category against ground-truth labels (`true_category`), under strict, completed-only, and lenient (accepting `secondary_category`) rules.
  2. **Signal extraction:** Token-level precision, recall, and F1 over signal vocabulary identifiers, plus quote verbatim verification.
  3. **Priority assignment:** Deterministic evaluation of `evaluate_priority` applied to predicted signals vs ground truth `true_priority`, tracking under-prioritisation, over-prioritisation, and missed-high rates.
  4. **Queue routing:** Target queue selection compared with ground-truth queue mapping (including escalations override).
  5. **Draft reply sanity (optional sample):** Deterministic review flags (unknown placeholders, invented numbers, invented identifiers, overpromising words, invalid policy refs, contact details).
- **What is NOT evaluated:**
  1. The LLM does not generate priority or queue values directly; priority and queue accuracy evaluate whether extracted signals correctly trigger the deterministic business rules.
  2. Automated draft checks do not evaluate prose quality, tone, empathy, or nuanced policy interpretation; human operator review remains the primary control.
  3. Real customer data is never used; evaluation is conducted strictly on synthetic test tickets.

## 3. The Integrity Rule
`data/eval_tickets.json` is a fixed, held-out TEST SET.
- **Strict Freeze:** Prompts, queue descriptions in `config/queues.yaml`, signal definitions in `config/priority_rules.yaml`, and classification code must NEVER be modified, tuned, or prompt-engineered in response to evaluation benchmark results.
- **Config Fingerprinting:** Every evaluation run computes and records a SHA-256 fingerprint over:
  - Classification system prompt template
  - Draft system prompt template
  - Bytes of `config/queues.yaml`
  - Bytes of `config/priority_rules.yaml`
  - Bytes of `data/eval_tickets.json`
  - Provider model name, temperature (0.0), reasoning effort, and maximum output tokens.
  Any change to prompts, rules, test set bytes, or model configuration immediately changes the run fingerprint, preventing unreported model tuning.

## 4. Metric Definitions

### 4.1 Wilson 95% Score Confidence Interval
For observed success count $k$ over $n$ trials with $z = 1.96$:
$$p = \frac{k}{n}$$
$$\text{denominator} = 1 + \frac{z^2}{n}$$
$$\text{center} = \frac{p + \frac{z^2}{2n}}{\text{denominator}}$$
$$\text{margin} = \frac{z \sqrt{\frac{p(1 - p)}{n} + \frac{z^2}{4n^2}}}{\text{denominator}}$$
$$\text{low} = \max(0.0, \text{center} - \text{margin})$$
$$\text{high} = \min(1.0, \text{center} + \text{margin})$$
When $n = 0$, the interval is `None`.

### 4.2 Category Accuracy
- **Strict Category Accuracy:** $\frac{\text{tickets where predicted\_category == true\_category}}{n_{\text{evaluated}}}$
  *Failed items are counted as wrong.*
- **Completed-Only Category Accuracy:** $\frac{\text{tickets where predicted\_category == true\_category}}{n_{\text{completed}}}$
- **Lenient Category Accuracy:** Correct if `predicted_category` matches `true_category` OR `secondary_category` (when non-null).

### 4.3 Per-Category Metrics & Macro-F1
For each category $c$:
- $\text{Support}: \text{Count of evaluated tickets with } \text{true\_category} == c$.
- $\text{Predicted}: \text{Count of evaluated tickets with } \text{predicted\_category} == c$.
- $\text{Precision} = \frac{\text{TP}}{\text{Predicted}}$ (null if Predicted is 0).
- $\text{Recall} = \frac{\text{TP}}{\text{Support}}$ (null if Support is 0).
- $\text{F1} = \frac{2 \times P \times R}{P + R}$ (0 if $P+R=0$ or either is null).
- **Macro-F1:** Unweighted arithmetic mean of F1 scores across all categories with $\text{Support} > 0$.

### 4.4 Category Confusion Matrix
A matrix where rows represent ground-truth categories and columns represent predicted categories, with an additional final `no_prediction` column accounting for failed tickets.

### 4.5 Priority Metrics
Priority ordering: `low` (rank 1) < `medium` (rank 2) < `high` (rank 3).
- **Priority Accuracy:** Correct priority matches over all evaluated (failed items counted wrong) and completed-only.
- **3x3 Confusion Matrix:** True priority (rows) vs predicted priority (columns) plus `no_prediction`.
- **Under-prioritised:** Completed tickets where $\text{predicted\_rank} < \text{true\_rank}$ (count and % of completed).
- **Over-prioritised:** Completed tickets where $\text{predicted\_rank} > \text{true\_rank}$ (count and % of completed).
- **Missed-High Rate:** Completed tickets with $\text{true\_priority} == \text{high}$ but predicted lower (`low` or `medium`), divided by completed true-high tickets. True-high tickets with no prediction (failed runs) are tracked separately as `truth_high_no_prediction` and NOT counted as under-prioritised.

### 4.6 Queue Accuracy
Accuracy of predicted queue versus ground-truth queue determined by evaluating deterministic rules on ground-truth signals and categories (including escalation overrides).

### 4.7 Reviewer Change Proxy
Share of evaluated tickets where category, priority, or queue is incorrect OR there is no prediction.
> [!NOTE]
> This is an automated proxy reflecting where an operator would need to alter an agent recommendation; it is not a measured production override rate.

### 4.8 Signal Metrics
- **Micro Precision, Recall, F1:** Aggregated across all individual signal tokens for completed tickets.
- **Exact Set Match Rate:** Proportion of completed tickets where `set(predicted_signals) == set(true_signals)`.
- **Per-Signal Breakdown:** Support, predicted count, precision, recall for each configured signal.

### 4.9 Priority Errors by Cause
For completed tickets with mismatched priority:
- `missing_true_signal`: Model omitted a ground-truth signal that would have triggered the correct rule, with no extra signals.
- `extra_signal`: Model extracted an extra signal that triggered a higher rule, with no missing signals.
- `both`: Both missing and extra signals present.
- `signals_exact_but_priority_wrong`: Mathematically 0 by construction, proved by property-based testing.

### 4.10 Slices
Slices evaluate performance across subsets:
- **Language:** `en` vs `hinglish`.
- **Ambiguity:** `is_ambiguous` true vs false.
- **Short Body:** Word count $< 12$ words.
- **Urgency or Delay:** `true_signals` contains `explicit_urgency` or `delivery_delayed_over_3_days`.
Slices with sample size $n < 30$ are explicitly labelled as `low_confidence = true`.

### 4.11 Quote Verification & Flags
- Total predicted signals, verified verbatim quotes, verification rate, and count of `high_stakes_signal_unverified` flags.
- Failure counts categorized by specific error code (`llm_timeout`, `llm_output_truncated`, `invalid_structure`, etc.).

### 4.12 Failure Case Selection
The top 5 failure cases displayed in results are selected deterministically using this exact priority ordering:
1. Missed high priority: true priority high, predicted lower.
2. Wrong category.
3. Wrong priority.
4. No prediction (failed ticket).
Ties are broken deterministically by `ticket_id` ascending.

## 5. Resumability, Pacing, and Rate Limits
- **Pacing:** An interval of `EVAL_PACING_SECONDS` (default: 2s) is inserted between ticket calls to avoid provider throttling.
- **Rate Limit Backoff:** On `LLMRateLimited`, the runner waits for the provider's `retry_after_seconds` (or 60s), up to `EVAL_MAX_RATE_LIMIT_WAITS` (default: 3) per ticket, capped at `EVAL_MAX_WAIT_SECONDS` (default: 120s) per wait. If exceeded, the run pauses with the ticket pending.
- **Immediate Pause:** On `LLMQuotaExhausted`, `LLMAuthError`, or `LLMModelNotFound`, the run pauses immediately without marking the ticket as failed.
- **Resumption:** Paused runs can be resumed via `POST /api/engagements/{id}/evaluation/runs/{rid}/resume`. Completed items are retained; pending and transiently failed tickets are re-executed.

## 6. Privacy & Data Handling
- Only synthetic ticket subject, body, and channel are sent to the AI provider inside standard delimiters (`<ticket>...</ticket>`).
- Ground-truth labels (`true_category`, `true_signals`, `true_priority`, `secondary_category`, `is_ambiguous`) are NEVER transmitted to the provider.
- Draft reply text is evaluated in memory and discarded; only flag codes, reply length, and policy ref validity are persisted.
- Audit logs record aggregate run statistics (`eval_started`, `eval_completed`, `eval_paused`, `eval_cancelled`), never ticket text or prompts.

## 7. Limitations
1. **Synthetic Test Data:** Evaluation tickets were authored synthetically from templates. Label correctness is defined by construction rather than real-world customer consensus.
2. **Single-Run Variance:** Even at temperature 0.0, commercial LLM providers exhibit non-deterministic outputs across dates and server loads.
3. **Slice Confidence:** Slice sample sizes (especially Hinglish or ambiguous tickets) are small; confidence intervals are broad.
4. **Proxy vs Reality:** The reviewer-change proxy estimates where an operator would disagree with the model, not whether human operators actually catch or correct these errors in live triage.
