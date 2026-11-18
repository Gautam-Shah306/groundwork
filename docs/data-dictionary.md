# Groundwork — Synthetic Data Dictionary

> **Synthetic data notice:** All records in `data/sample_tickets.csv`, `data/eval_tickets.json`, and `data/answer_key.json` belong to the fictional e-commerce company **Kora Living** and are generated deterministically by `scripts/generate_data.py` (fixed seed `42`).

---

## 1. Operational Ticket Dataset (`data/sample_tickets.csv`)

- **Rows:** 2,000 rows (1,997 base tickets + 3 intentionally injected duplicate `ticket_id` rows).
- **Period:** Monday `2026-09-07T00:00:00+05:30` through Sunday `2026-11-01T23:59:59+05:30` (8 weeks).
- **Timestamp format & timezone:** ISO 8601 (`YYYY-MM-DDTHH:MM:SS+05:30`) with explicit India Standard Time (`+05:30`) offset. Empty string (`""`) denotes a missing timestamp.

| Field | Type | Meaning | Allowed Values / Format |
|---|---|---|---|
| `ticket_id` | string | Ticket identifier | `KL-000001` .. `KL-001997` (3 intentional duplicates injected) |
| `created_at` | ISO 8601 timestamp | Ticket creation timestamp | `YYYY-MM-DDTHH:MM:SS+05:30` within the 8-week period |
| `assigned_at` | ISO 8601 timestamp | Timestamp when ticket was manually assigned to an agent | `YYYY-MM-DDTHH:MM:SS+05:30` (`>=` next shift start `09:00+05:30` for overnight tickets) |
| `first_response_at` | ISO 8601 timestamp (nullable) | Timestamp of the first agent response | `YYYY-MM-DDTHH:MM:SS+05:30` or empty (includes injected missing and pre-creation anomalies) |
| `resolved_at` | ISO 8601 timestamp (nullable) | Timestamp of ticket resolution | `YYYY-MM-DDTHH:MM:SS+05:30` for resolved tickets, empty for `open`/`pending` (includes injected missing and `>300d` anomalies) |
| `category` | enum string | Support issue category | Vocabulary in Section 2 plus 6 injected `billing_misc` rows |
| `priority` | enum string | Historical human-assigned priority | `low`, `medium`, `high` |
| `queue` | enum string | Support team queue | Vocabulary in Section 2 |
| `assigned_agent` | string | Handling agent identifier | `Agent 01` .. `Agent 12` (`Agent 01..09` day shift `09:00–18:00 IST`; `Agent 10..12` late shift `14:00–22:00 IST`) |
| `status` | enum string | Ticket lifecycle state | `resolved`, `pending`, `open` |
| `channel` | enum string | Customer contact channel | `email`, `chat`, `web_form`, `whatsapp` |
| `reassignment_count` | integer | Number of times ticket was reassigned between queues | Non-negative integer (`0`, `1`, `2`) |
| `customer_id` | string | Anonymised synthetic customer identifier | `CUST-0001` .. `CUST-1300` (~1,280 distinct with repeats) |

---

## 2. Controlled Vocabularies

### Categories & Queues (`config/queues.yaml`)

| Category ID | Display Name | Mapped Queue |
|---|---|---|
| `order_tracking` | Order tracking | `Order support` |
| `address_change` | Address change | `Order support` |
| `returns_refunds` | Returns and refunds | `Returns and refunds` |
| `damaged_item` | Damaged item | `Returns and refunds` |
| `payment_issues` | Payment issues | `Payments` |
| `product_questions` | Product questions | `General` |
| `account_login` | Account and login | `General` |

Additional escalation-only queue: **`Escalations`** (used via deterministic `queue_override` for rule `R-LEGAL`).

### Channels
`email`, `chat`, `web_form`, `whatsapp`

### Statuses
`resolved`, `pending`, `open`

### Priorities
`low`, `medium`, `high`

---

## 3. Closed Signal Vocabulary (`config/priority_rules.yaml`)

| Signal | Definition |
|---|---|
| `payment_charged_twice` | Customer reports duplicate or repeated charges for the same order. |
| `payment_deducted_order_failed` | Payment was debited from the customer account but order confirmation failed. |
| `item_damaged_or_defective` | Delivered item arrived cracked, broken, scratched, or non-functional. |
| `wrong_item_received` | Delivered parcel contains a different product, size, or finish than ordered. |
| `delivery_delayed_over_3_days` | Shipment has passed its expected delivery window by more than three days or tracking has stalled over three days. |
| `explicit_urgency` | Customer states a hard deadline, event date, or urgent time sensitivity. |
| `refund_overdue` | Expected refund has not arrived within the stated five-to-seven business day window. |
| `legal_or_chargeback_threat` | Customer threatens legal action, consumer court complaint, or bank chargeback. |
| `account_locked` | Customer cannot sign in, is locked out, or cannot complete password reset. |
| `general_inquiry` | Routine product, care, availability, or policy question with no urgent issue. |

---

## 4. Triage Evaluation Set Schema (`data/eval_tickets.json`)

JSON array of **150** synthetic support tickets used exclusively for offline triage evaluation and scoring (ground-truth fields are never passed to the LLM).

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique evaluation ID (`EV-001` .. `EV-150`) |
| `subject` | string | Ticket subject line |
| `body` | string | Customer message body (all 150 bodies unique) |
| `channel` | enum string | One of `email`, `chat`, `web_form`, `whatsapp` |
| `language` | enum string | `en` or `hinglish` (`>= 10` Hinglish tickets) |
| `true_category` | enum string | Primary ground-truth category from `config/queues.yaml` (`>= 12` per category) |
| `true_signals` | list[string] | Ground-truth signals from the closed signal vocabulary |
| `true_priority` | enum string | Deterministic priority equal to `evaluate_priority(true_signals).priority` |
| `is_ambiguous` | boolean | Whether the ticket straddles two categories (`>= 15` true) |
| `secondary_category` | enum string \| null | Secondary category when `is_ambiguous` is `true`, else `null` |

---

## 5. Answer Key Rule (`data/answer_key.json` — R6)

`data/answer_key.json` documents the fixed generator seed (`42`), intended planted operational causes, exact injected data-quality counts, and measured planted-effect numbers.

**Non-negotiable rule (R6):** `data/answer_key.json` is strictly for **automated tests and documentation only**. Application code under `backend/app/` must **never** import, open, read, or expose `data/answer_key.json` to any API response or LLM prompt.
