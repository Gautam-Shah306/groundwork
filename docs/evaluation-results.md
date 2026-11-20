# Support Triage Evaluation Benchmark Results

> **IMPORTANT INTEGRITY NOTICE:** The evaluation dataset (`data/eval_tickets.json`) is a held-out test set. It must NEVER be used to train, tune, or optimize prompts, triage categories, or priority rules.

**Measured outcome on synthetic tickets. Single run.**

## Run Metadata
- **Evaluation Run ID:** 2
- **Model:** `openai/gpt-oss-20b`
- **Configuration Fingerprint:** `a29dcf7167a74cd129c9c922d2705e07b8dade7c4c60dfc87e012ffd8fa78c12`
- **Date & Time:** `2026-11-20T04:58:20.794051Z`
- **Duration:** 840 s (~14 min)
- **Total Provider Calls:** 171
- **Total Tokens:** 201,870
- **Evidence File:** `local/evidence/9b/c5_full_run.json` (SHA256: `0895b4a3ee3c37f6056f02d304bad4820bddeb2e91f662773236c14a552ce4db`)

## Headline Metrics
- **Total Tickets Evaluated (n):** 150
- **Completed:** 148
- **Failed:** 2
- **Strict Category Accuracy:** 90.7% (0.9067) | Wilson 95% CI: [84.9%, 94.4%]
- **Completed Category Accuracy:** 91.9% (0.9189)
- **Lenient Category Accuracy:** 93.3% (0.9333)
- **Priority Accuracy:** 74.0% (0.7400)
- **Completed Priority Accuracy:** 75.0% (0.7500)
- **Queue Routing Accuracy:** 92.0% (0.9200)
- **Reviewer-Change Proxy:** 34.0% (0.3400)
- **Macro F1 (Category):** 0.9133
- **Signal Micro F1:** 0.8220
- **Exact Signal Set Match Rate:** 65.3% (0.6533)

## Per-Category Performance
| Category ID | Support | Predicted Count | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `account_login` | 19 | 16 | 1.0000 | 0.8421 | 0.9143 |
| `address_change` | 20 | 20 | 1.0000 | 1.0000 | 1.0000 |
| `damaged_item` | 22 | 17 | 0.9412 | 0.7273 | 0.8205 |
| `order_tracking` | 23 | 25 | 0.8800 | 0.9565 | 0.9167 |
| `payment_issues` | 23 | 20 | 1.0000 | 0.8696 | 0.9303 |
| `product_questions` | 20 | 21 | 0.9048 | 0.9500 | 0.9268 |
| `returns_refunds` | 23 | 29 | 0.7931 | 1.0000 | 0.8846 |

## Category Confusion Matrix
| True \ Pred | `account_login` | `address_change` | `damaged_item` | `order_tracking` | `payment_issues` | `product_questions` | `returns_refunds` | `no_prediction` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `account_login` | 16 | 0 | 0 | 1 | 0 | 0 | 0 | 2 |
| `address_change` | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| `damaged_item` | 0 | 0 | 16 | 0 | 0 | 0 | 6 | 0 |
| `order_tracking` | 0 | 0 | 1 | 22 | 0 | 0 | 0 | 0 |
| `payment_issues` | 0 | 0 | 0 | 1 | 20 | 2 | 0 | 0 |
| `product_questions` | 0 | 0 | 0 | 1 | 0 | 19 | 0 | 0 |
| `returns_refunds` | 0 | 0 | 0 | 0 | 0 | 0 | 23 | 0 |

## Priority Metrics & Confusion
- **Under-prioritised:** 6 (4.05%)
- **Over-prioritised:** 31 (20.95%)
- **Missed-High Priority:** 4 tickets (7.69%)
- **Truth-High No Prediction:** 0
- **Priority Errors by Cause:**
  - `signals_exact_but_priority_wrong`: 0
  - `signals_missed`: 33
  - `signals_spurious`: 2
  - `signals_both`: 2
  - `model_failure`: 2

### Priority Confusion Matrix
| True \ Pred | `high` | `medium` | `low` | `no_prediction` |
| :--- | :---: | :---: | :---: | :---: |
| `high` | 48 | 4 | 0 | 0 |
| `medium` | 2 | 48 | 2 | 0 |
| `low` | 0 | 29 | 15 | 2 |

## Subgroup Slices
| Slice Name | Count (n) | Category Accuracy | Priority Accuracy | Low Confidence Flag |
| :--- | :---: | :---: | :---: | :---: |
| `en` | 136 | 90.4% | 72.1% | No |
| `hinglish` | 14 | 92.9% | 92.9% | Yes (n < 30) |
| `is_ambiguous` | 19 | 79.0% | 89.5% | Yes (n < 30) |
| `short` | 14 | 92.9% | 85.7% | Yes (n < 30) |
| `urgency_or_delay` | 43 | 93.0% | 90.7% | No |

## Draft Response Quality Checks
- **Sampled Drafts (n):** 21
- **Tickets with Review Flags:** 4
- **Flag Rate:** 19.1%
- **Unflagged Rate:** 81.0%
- **Flag Counts by Code:** `{'overpromise_wording': 4}`
- **Note:** Automated checks only: this does not measure reply quality.

## Top Failure Cases (Identified by Ticket ID)
| Ticket ID | True Category | Predicted Category | True Priority | Predicted Priority | Severity Reason |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `EV-075` | `returns_refunds` | `returns_refunds` | `high` | `medium` | High priority ticket under-prioritised to medium. |
| `EV-122` | `damaged_item` | `returns_refunds` | `high` | `medium` | High priority ticket under-prioritised to medium. |
| `EV-125` | `damaged_item` | `returns_refunds` | `high` | `medium` | High priority ticket under-prioritised to medium. |
| `EV-130` | `damaged_item` | `returns_refunds` | `high` | `medium` | High priority ticket under-prioritised to medium. |
| `EV-008` | `damaged_item` | `returns_refunds` | `high` | `high` | Category misclassified as returns_refunds (expected damaged_item). |

## Evaluation Limitations
1. **Synthetic Data Realism:** All evaluation tickets are synthetically generated for Kora Living. Performance reflects synthetic distributional patterns and may differ in actual production customer support.
2. **Proxy Metric Constraints:** The reviewer-change proxy treats any difference in category, priority, or queue as requiring human intervention, which represents a conservative operational upper bound.
3. **Single Run Variance:** Benchmark results reflect a single pass against `openai/gpt-oss-20b` (temperature 0). Natural provider latency, network timeouts, and token limits account for failed items (2 tickets).
4. **Draft Reply Scope:** Draft evaluations inspect structural policy compliance, placeholders, and overpromising rules; automated checks do not evaluate tone or resolution depth.
