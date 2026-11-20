# Overview Reconciliation and Verification

**Date:** 2026-11-20  
**Commit (HEAD):** `ecd13a1887146bf17240d2c2fc68f73350db3b5e`  
**Decision Branch:** Branch A (all evaluation numbers match stored summary and `docs/evaluation-results.md` exactly; all ticket IDs exist in `data/eval_tickets.json`).

---

## 1. Document Reconciliation Status

`docs/overview.md` was **absent** (untracked and not present in the workspace) at the start of Prompt 11. Per instruction B1, direct textual reconciliation is skipped with `NOT DONE (file absent)`. In its place, this document records the complete, verified inventory of Groundwork facts, numbers, IDs, and vocabulary established in Prompt 11.

---

## 2. Verified Repository Facts (from `local/facts.py`)

| Category / Item | Claim / Verified Fact | Source of Truth | Verification Status |
| :--- | :--- | :--- | :--- |
| **Category Vocabulary** | `order_tracking`, `returns_refunds`, `payment_issues`, `product_questions`, `address_change`, `damaged_item`, `account_login` (7 total) | `config/queues.yaml` | **VERIFIED** |
| **Routing Queues** | `Order support`, `Returns and refunds`, `Payments`, `General`, `Escalations` (5 total) | `config/queues.yaml` | **VERIFIED** |
| **Signal Definitions** | `payment_charged_twice`, `payment_deducted_order_failed`, `item_damaged_or_defective`, `wrong_item_received`, `delivery_delayed_over_3_days`, `explicit_urgency`, `refund_overdue`, `legal_or_chargeback_threat`, `account_locked`, `general_inquiry` (10 total) | `config/priority_rules.yaml` | **VERIFIED** |
| **Priority Rules** | `R-LEGAL`, `R-PAY`, `R-DAMAGE`, `R-DELAY-URGENT`, `R-REFUND`, `R-DELAY`, `R-URGENT`, `R-ACCOUNT`, `R-GENERAL` (9 total) | `config/priority_rules.yaml` | **VERIFIED** |
| **Allowed Placeholders** | `[CUSTOMER_NAME]`, `[ORDER_ID]`, `[TRACKING_STATUS]`, `[REFUND_AMOUNT]`, `[DELIVERY_DATE]`, `[AGENT_NAME]` (6 total) | `app/triage/prompts.py` | **VERIFIED** |
| **Deterministic Metrics** | 18 registered metrics in `METRIC_REGISTRY` | `app/metrics/registry.py` | **VERIFIED** |
| **Eval Dataset Schema** | 10 real keys: `id`, `subject`, `body`, `channel`, `language`, `true_category`, `true_signals`, `true_priority`, `is_ambiguous`, `secondary_category` | `data/eval_tickets.json` | **VERIFIED** |
| **Eval Dataset Size** | Exactly 150 tickets | `data/eval_tickets.json` | **VERIFIED** |
| **Eval Language Split** | 136 English (`en`), 14 Hinglish (`hinglish`) | `data/eval_tickets.json` | **VERIFIED** |
| **Eval Ambiguity Split** | 131 clear (`is_ambiguous: false`), 19 ambiguous (`is_ambiguous: true`) | `data/eval_tickets.json` | **VERIFIED** |
| **Eval Short Body Split** | 136 standard ($\ge 12$ words), 14 short ($< 12$ words) | `data/eval_tickets.json` | **VERIFIED** |
| **Classification Prompt Hash** | `b7a4c9704030f34faffcb6cee563fe9b8764dbc887bce213f9cd74c0bf9877d0` | `app/triage/prompts.py` | **VERIFIED** (equals p10 hash) |
| **Provider Interface** | `generate(self, system, messages, tools, max_output_tokens, temperature)` | `app/llm/base.py` | **VERIFIED** |
| **Git Tags** | 13 tags: `p01`–`p10`, `p06b`, `p08b`, `p09b` | `.git/refs/tags`, `packed-refs` | **VERIFIED** |
| **Backend Test Count** | 465 passed tests across 29 test files; overall coverage 91.84% | `pytest --cov=app` | **VERIFIED** |
| **Frontend Test Count** | 192 passed tests across 12 test files | `vitest run` | **VERIFIED** |

---

## 3. Verified Stored Evaluation (Run 2)

All figures independently recomputed from raw stored item predictions and `data/eval_tickets.json` via `local/verify_run2.py`:

- **Total tickets evaluated:** 150 (148 completed, 2 failed due to provider rate-limit during run)
- **Strict category accuracy (all 150):** 0.9067 (90.7%)
- **Completed-only category accuracy:** 0.9189 (91.9%)
- **Lenient category accuracy:** 0.9333 (93.3%)
- **Priority accuracy (all 150):** 0.7400 (74.0%)
- **Completed priority accuracy:** 0.7500 (75.0%)
- **Queue routing accuracy (all 150):** 0.9200 (92.0%)
- **Reviewer change proxy:** 0.2867 (28.7%)
- **Missed high priority:** 4 tickets
- **Under-prioritised:** 6 tickets
- **Over-prioritised:** 31 tickets
