# Support Triage Automation & Human-in-the-Loop Architecture

## 1. Purpose & Core Principles

The Groundwork Triage Prototype (`Stage 03 Build`) assists human support operators by processing incoming customer tickets, extracting verified factual signals, classifying the issue, determining priority and routing via deterministic business rules, and drafting an empathetic, policy-grounded response.

In strict adherence to Groundwork's non-negotiable principles (`AGENTS.md`):
- **R1 / R4**: The LLM **NEVER** calculates, decides, or overrides business priority or ticket queue. Priority and queue routing are computed entirely by the deterministic priority engine in `backend/app/metrics/triage_priority.py` using priority rules from `config/priority_rules.yaml` and category routing from `config/queues.yaml`.
- **R2**: Every signal extracted by the model must cite a verbatim quote from the ticket body, verified deterministically against the source text.
- **R3**: **No customer-facing message is ever sent directly.** The agent proposes; a human operator reviews, edits, and either approves or rejects. Every human action is recorded in the immutable audit log (`EngagementAudit`). `record_human_decision` is intentionally **NOT** an LLM-callable tool.
- **R6 / R8**: Draft replies rely strictly on `knowledge/policies.md` and ticket contents. Unknown order or customer details become closed placeholder tokens (e.g., `[ORDER_ID]`), never hallucinated or invented facts.
- **R7**: All prototype outputs are explicitly labelled as `AI recommendation`, `Deterministic rule`, `Simulated result`, or `Approved action`.

---

## 2. Fixed Pipeline Architecture

The triage pipeline (`backend/app/triage/pipeline.py`) executes in a strictly sequential, four-step pipeline with an overall 90-second timeout:

```
[ Incoming Ticket ]
        │
        ▼
1. classify_ticket (LLM: temperature=0, no tools)
   ├── Primary category (closed vocabulary with descriptions)
   ├── Optional secondary category (if ticket clearly straddles issues)
   ├── Extracted signals with verbatim quotes (closed vocabulary)
   └── Brief AI rationale (<= 300 chars)
        │
        ▼
   [ Deterministic Post-Processing & Normalization ]
   ├── Quote verification (text_utils.normalize_text_for_comparison)
   ├── Unknown signal filter & quote absence flags
   └── Escalation & high-stakes signal check
        │
        ▼
2. recommend_priority (Deterministic Python Function)
   ├── Evaluates extracted signals via evaluate_priority()
   ├── Assigns priority (low, medium, high)
   ├── Identifies first-matching priority rule & definition
   ├── Determines target queue from config/queues.yaml
   └── Applies queue_override (e.g. Escalations queue)
        │
        ▼
3. draft_ticket_response (LLM: temperature=0, no tools)
   ├── Context: full text of knowledge/policies.md (< 12,000 chars)
   ├── Closed placeholder vocabulary
   ├── Draft reply (<= 1200 chars)
   ├── Policy references (exact policy headings)
   └── Reviewer note for operator
        │
        ▼
   [ Deterministic Draft Post-Processing ]
   ├── Checks for numbers not in policy or ticket
   ├── Checks for identifiers/order IDs not in ticket
   ├── Detects overpromising language (guarantee, promise, 100%)
   └── Verifies policy section headings & contact details
        │
        ▼
4. create_triage_proposal (Database Write)
   └── Persists TriageProposal (status: awaiting_approval)
```

### Determinism vs. LLM Separation
| Step | Execution | Offered Tools | Failure Behavior |
| :--- | :--- | :--- | :--- |
| `1. classify_ticket` | LLM (`openai/gpt-oss-20b`, `temperature=0`) | None | **Fatal**: fails pipeline; no proposal created. 1 repair attempt on schema error. |
| `2. recommend_priority` | Deterministic Python (`evaluate_priority`) | None | Deterministic rule engine; never fails on valid signal vocabulary. |
| `3. draft_ticket_response` | LLM (`openai/gpt-oss-20b`, `temperature=0`) | None | **Non-Fatal**: on failure or timeout, proposal is created with empty draft, flag `draft_unavailable`, and error details. |
| `4. create_triage_proposal` | SQLite Database Transaction | None | Atomic insert with unique constraint on `(engagement_id, ticket_hash)`. |

---

## 3. Data Model & Idempotency

### Schema (`TriageProposal`)
Stored in `triage_proposals` table:
- `id`: Integer primary key.
- `engagement_id`: Integer foreign key referencing `engagements.id`.
- `ticket_hash`: SHA-256 hex digest of normalized `subject`, `body`, and `channel` (`trim()`, whitespace collapsed, `lower()`).
- `subject`: String (optional, max 200 chars).
- `body`: Text (5–4,000 chars).
- `channel`: String (`email`, `chat`, `web_form`, `whatsapp`).
- `category`: String (primary category from `config/queues.yaml`).
- `secondary_category`: String | None (optional secondary category).
- `priority`: String (`low`, `medium`, `high`) computed deterministically.
- `queue`: String (target queue name from `config/queues.yaml`).
- `escalation`: Boolean (`true` if rule specified `queue_override: Escalations`).
- `rule_id`: String (deterministic rule ID that fired, e.g. `R-LEGAL`, `R-DOUBLE-CHARGE`).
- `rule_definition`: String (plain-language definition of the rule).
- `signals`: JSON array of `{signal: str, source_quote: str, quote_verified: bool}`.
- `draft_reply`: Text (drafted customer response, <= 1200 chars).
- `policy_refs`: JSON array of strings (exact policy section headings).
- `reviewer_note`: Text | None (internal guidance from model to reviewer).
- `flags`: JSON array of `{code: str, message: str, where: str}`.
- `tool_trace`: JSON array of execution steps (arguments contain lengths only, never ticket text).
- `model`: String (LLM model used).
- `usage`: JSON object (`prompt_tokens`, `completion_tokens`, `total_tokens`).
- `error`: JSON object | None.
- `status`: String (`awaiting_approval`, `approved`, `rejected`).
- `decided_by`: String | None (operator name on decision).
- `decided_at`: DateTime | None (timestamp of decision).
- `decision_reason`: String | None (optional operator reason, max 300 chars).
- `final_values`: JSON object | None (`{category, priority, queue, reply_text, edited_fields}`).
- `edited`: Boolean (default `false`, set to `true` if any final value differs from proposal).

### Idempotency
- A unique index exists on `(engagement_id, ticket_hash)`.
- If a ticket with identical normalized content is submitted again, the API catches the duplicate or unique constraint collision, does NOT call the LLM provider, and returns HTTP 200 with `{proposal: ..., duplicate: true}`.

---

## 4. Closed Vocabularies

### Categories (`config/queues.yaml`)
1. `order_status`: Inquiries about order shipping, tracking updates, and delivery timelines.
2. `returns_refunds`: Requests for return labels, refund status, exchanges, or cancellation.
3. `product_inquiry`: Questions about product dimensions, materials, assembly, or stock.
4. `billing_payment`: Issues with charges, duplicate payments, invoices, or payment methods.
5. `account_access`: Login difficulties, password resets, email updates, or account security.
6. `feedback_complaints`: Customer dissatisfaction, feedback, policy complaints, or escalation requests.

### Signals (`config/priority_rules.yaml`)
- `legal_threat`: Mention of legal counsel, lawsuits, regulatory agencies, or formal legal action.
- `chargeback_threat`: Threat to dispute payment or file a credit card chargeback.
- `payment_charged_twice`: Report of double billing or multiple charges for one order.
- `damaged_item`: Report of goods received broken, damaged, defective, or unusable.
- `delivery_delay`: Report of order delayed, tracking stalled, or missed delivery date.
- `urgent_need`: Explicit statement that delivery or resolution is needed urgently or by a deadline.
- `refund_overdue`: Report that an expected or approved refund has not appeared.
- `general_inquiry`: General inquiry with no reported issue, damage, delay, or urgency.

### Placeholders
- `[CUSTOMER_NAME]`
- `[ORDER_ID]`
- `[TRACKING_STATUS]`
- `[REFUND_AMOUNT]`
- `[DELIVERY_DATE]`
- `[AGENT_NAME]`

---

## 5. Post-Processing Review Flags

| Flag Code | Stage | Trigger Condition |
| :--- | :--- | :--- |
| `unknown_signal_dropped` | Classification | Signal extracted by LLM is not in `config/priority_rules.yaml`. Dropped from list. |
| `signal_quote_not_found` | Classification | Source quote for signal cannot be found verbatim in ticket body. |
| `signal_without_quote` | Classification | Model extracted a signal without providing a `source_quote`. |
| `secondary_equals_primary` | Classification | Secondary category matches primary category. Secondary set to `null`. |
| `no_signals_extracted` | Classification | Informational flag: model extracted zero signals from ticket. |
| `high_stakes_signal_unverified` | Classification | A signal triggering high priority or escalation has an unverified quote. |
| `unknown_placeholder` | Drafting | A bracketed token `[...]` in draft reply is not in the allowed placeholder vocabulary. |
| `number_not_in_policy_or_ticket`| Drafting | A digit sequence appears in reply that is in neither `policies.md` nor the ticket text. |
| `identifier_not_in_ticket` | Drafting | An order-id-like pattern (e.g. `KL-12345`) appears in reply that was NOT in the ticket. |
| `overpromise_wording` | Drafting | Reply contains unconditional commitment words (`guarantee`, `guaranteed`, `promise`, `definitely`, `100%`). |
| `unknown_policy_ref` | Drafting | Cited policy heading is not an exact section heading in `knowledge/policies.md`. |
| `contact_detail_not_in_policy` | Drafting | Emails, phone numbers, or URLs appear in reply that are absent from `policies.md`. |
| `draft_unavailable` | Drafting | Draft step failed (token limit, parsing error, or timeout). Proposal created with empty reply. |

---

## 6. Human Decision Rules & Audit Trail

- **Awaiting Approval**: Every new proposal starts in `awaiting_approval`.
- **Review & Edit**: Operators can inspect the full ticket, AI classification, deterministic rule reasoning, verified signal quotes, and draft reply. Operators may edit category, priority, queue, or reply text.
- **Atomic State Transitions**: Decision updates execute conditionally: `UPDATE triage_proposals ... WHERE id = :id AND status = 'awaiting_approval'`.
- **Concurrency Guard**: If another operator or session decided the proposal, 0 rows update, returning HTTP 409 `already_decided`.
- **Approve Requirements**: Approval requires a non-empty `reply_text` (max 2000 chars). Approving with remaining placeholders is permitted; the response warns of `unresolved_placeholders`.
- **Reject Requirements**: Rejection requires no reply and takes an optional `reason` (max 300 chars).
- **Audit Logging**: Every proposal generation writes a `triage_proposed` event. Every decision writes a `triage_decision` event to `EngagementAudit`.
- **Zero Data Leakage**: Audit events store counts and metadata only (proposal ID, category, priority, queue, rule ID, edited fields, flag count, placeholder count). **Audit entries NEVER contain customer ticket text, reply text, quotes, or secrets.**

---

## 7. Privacy & Data Boundaries

- **What is sent to the LLM provider**:
  - The ticket `subject` and `body` (strictly encapsulated in untrusted `<ticket>` delimiters with internal closing tags neutralised).
  - Category names and one-line descriptions.
  - Priority signal definitions.
  - In the drafting step: the static text of `knowledge/policies.md` (validated $\le 12,000$ chars).
- **What is NEVER sent to the LLM provider**:
  - Customer contact records, CRM databases, or payment tokens.
  - Audit logs or user session IDs.
  - The answer key file (`data/answer_key.json`).
  - Outbound email or messaging credentials.

---

## 8. Limitations

1. **Heuristic Flags**: Post-processing review flags are deterministic sanity checks. They detect unverified numbers and overpromising words, but cannot substitute for human review. The review flags do not detect remedies beyond policy, so an empty flag list does not mean a reply is policy-safe and human review remains the control.
2. **Quote Verification Scope**: Signal quote verification proves a quote exists verbatim in the ticket, not that it was interpreted correctly.
3. **Language Scope**: Draft responses are generated in English only. Non-English tickets (e.g. Hinglish) are flagged for human operator handling.
4. **No Customer Dispatch**: The application contains no email or SMS dispatch code (`smtplib`, Twilio, SendGrid, etc.). The agent proposes; the human decides.
