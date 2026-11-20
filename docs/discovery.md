# Groundwork Discovery Workspace

The Discovery workspace structures qualitative client statements, interview notes, and operational context into a testable problem brief before quantitative diagnostics begin.

## Purpose

Consultants often begin an engagement with ambiguous, subjective client complaints (e.g. *"Customers wait too long for replies, with high backlog"*). The Discovery workspace enables operators to:
1. Capture qualitative interview notes from stakeholders (support leads, agents, engineering).
2. Use an AI discovery analyst to synthesize interview evidence into structured, testable problem briefs.
3. Enforce deterministic rigor through post-processing checks that verify verbatim source quotes, flag ungrounded numbers, enforce hypothesis hedging, and disallow causal wording.
4. Maintain a 5-version snapshot history with restore capabilities to protect manual edits against unintended AI overwrites.

---

## Schema & Structure (`BriefSections`)

All problem briefs conform to the `BriefSections` schema (`backend/app/discovery/schema.py`). Every section enforces strict character limits and item caps:

| Section | Cap / Limit | Description | Required Quotes |
| :--- | :--- | :--- | :---: |
| `context` | 1,500 chars | High-level client and operational environment summary | No |
| `problem_statement` | 500 chars | Standardized, non-causal problem statement template | No |
| `themes` | 8 items | Dominant operational themes extracted from interviews | Yes |
| `stakeholders` | 8 items | Key roles, teams, and departments affected | Yes |
| `workflow_steps` | 8 items | Sequential lifecycle or operational steps described | Yes |
| `symptoms` | 8 items | Observed friction points and customer pain points | Yes |
| `impact` | 8 items | Business and operational consequences | Yes |
| `known_facts` | 12 items | Qualitative client statements or verified observed facts | Yes |
| `hypotheses` | 8 items | Hedged working theories to test quantitatively | No |
| `assumptions` | 8 items | Unverified working beliefs held by the team | No |
| `unknowns` | 8 items | Explicit gaps in current organizational knowledge | No |
| `candidate_kpis` | 5 items | Candidate metric IDs from the Groundwork metrics registry | No |
| `follow_up_questions`| 12 items | Open, asked, or answered clarifying questions | No |

### Standard Item Schema (`Item`)
Every item in list sections contains:
- `id`: Unique 8-character hex string.
- `text`: Concise item content ($\le 300$ chars).
- `source_quote`: Optional verbatim quote from interview notes (the Prompt 7 spec said 240 characters; 400 was an implementation decision and remains the validation cap; the discovery prompt asks for short single-sentence fragments of at most 200 characters).
- `quote_verified`: Boolean set by post-processing (`true` if found in source text, `false` otherwise).
- `origin`: `"ai"` or `"user"`.
- `status`: `"ai_draft"`, `"user_edited"`, or `"confirmed"`.
- `flags`: List of review flag codes.

### Known Fact Items (`KnownFactItem`)
Items in `known_facts` distinguish between:
- `client_statement`: Qualitative assertions made during stakeholder interviews.
- `observed_fact`: Verified quantitative assertions. Must provide a non-empty `source` referencing a dataset or verified document.

---

## UI Token & Label Mapping

In adherence to `docs/design-system.md` (R9), every piece of evidence and draft item is rendered with explicit type and origin labels:

- **AI draft**: Marked with `Simulated result` / `AI recommendation` and amber StatusPills.
- **Client statement**: Marked with `Client statement` (`<TypeLabel kind="Client statement">`).
- **Hypothesis**: Carries `<StatusPill tone="amber">Needs validation</StatusPill>` and `<TypeLabel kind="Hypothesis">`.
- **Observed fact**: Marked with `<TypeLabel kind="Observed fact">` and displays verified source.
- **Confirmed items**: Marked with `<StatusPill tone="emerald">Confirmed</StatusPill>`.

---

## AI Discovery Pipeline

The AI analysis pipeline runs synchronously via `POST /api/engagements/{id}/discovery/analyse`:

```
Selected Interview Notes
        │
        ▼
Neutralized Data Block (delimiters escaped, <= 30,000 chars)
        │
        ▼
LLM Generation (Groq / Gemini)
        │
        ├── Initial JSON Parse Success ──┐
        │                                │
        └── Invalid JSON / Schema Error  │
                     │                   │
                     ▼                   │
             One-shot Repair Loop        │
                     │                   │
                     └───────────────────┤
                                         ▼
                          Deterministic Post-Processing
                          ├── Quote Substring Verification
                          ├── Number Token Matching
                          ├── Hypothesis Hedge Checking
                          ├── Causal Language Banning
                          └── Metrics Registry KPI Filter
                                         │
                                         ▼
                            DiscoveryAnalysis Record
```

### Deterministic Post-Processing Flags

1. `quote_not_found`: `source_quote` does not appear verbatim (with whitespace, quote, and case normalization) in interview notes or client statements.
2. `quote_missing`: An item in a quote-requiring section (`themes`, `symptoms`, `impact`, `known_facts`, etc.) is missing a `source_quote`.
3. `number_not_in_notes`: A number mentioned in an item's text does not appear in the source notes.
4. `not_hedged`: A hypothesis lacks required modal hedging language (`may`, `might`, `could`, `possibly`).
5. `causal_wording`: Problem statement or hypothesis contains banned causal words (`because`, `caused`, `causes`, `due to`, `leads to`, `led to`, `result of`, `resulting from`, `drives`, `driven by`).
6. `invalid_kpi_dropped`: A candidate KPI metric ID is not among the 16 approved metrics in `backend/app/metrics/registry.py` and was removed.
7. `type_downgraded`: An item returned by the model as `observed_fact` was automatically downgraded to `client_statement`.

---

## Version History & Safeguards

- **5-Version Cap**: Up to 5 most recent snapshots per engagement are retained in the `brief_versions` table. Older versions are pruned automatically.
- **Overwrite Protection (`would_overwrite_edits`)**: When applying an AI draft (`POST /discovery/analyses/{aid}/apply`) over a brief that has manual edits (`source == 'edited'`), the API rejects the request with HTTP 409 unless `confirm_replace: true` is sent.
- **Audit Logging**: Every analysis, brief edit, draft application, and version restoration is written to `audit_logs` without leaking sensitive interview text or API keys.

---

## Data Isolation & Privacy

- **What is sent to the LLM**: Only engagement metadata (`name`, `client_name`, `industry`, `client_statement`) and the text of explicitly selected interview notes within escaped `<<<NOTE_START>>>` delimiters.
- **What is NEVER sent**: Ticket row data, metrics tables, database primary keys, audit logs, or answer key files.
- **Token Limits**: Discovery analysis requests use `LLM_DISCOVERY_MAX_OUTPUT_TOKENS` (default 6,000) to accommodate comprehensive structured briefs.
