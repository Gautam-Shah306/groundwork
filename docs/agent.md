# Groundwork — Investigation Agent Architecture & Grounding Specification

The Groundwork Investigation Assistant enables operators on the **Diagnostics** screen to ask natural-language questions about the currently loaded operational dataset while preserving strict determinism (`R1`), evidence traceability (`R2`), separation of business logic from AI orchestration (`R4`), Pydantic tool validation (`R5`), and privacy (`R6`).

---

## 1. Architecture

```text
Diagnostics UI (AssistantPanel)
   │  POST /api/engagements/{id}/assistant/runs  -> 202 { run_id, status: "running" }
   │  GET  /api/engagements/{id}/assistant/runs/{run_id}  (polled every 1s)
   ▼
FastAPI Assistant Router (backend/app/api/assistant.py)
   │  1. Validates engagement, question (1–1000 chars), LLM configuration, active dataset,
   │     and single-active-run guard (409 run_in_progress).
   │  2. Persists AgentRun (status="running") + AuditLog (actor="Demo operator", action="assistant_question").
   │  3. Starts background execution thread with its own SQLite session.
   ▼
Investigation Loop (backend/app/agent/loop.py)
   │  Single-turn bounded loop (max 6 round trips, max 10 tool calls, 60s overall timeout).
   │  Sends ONLY: SYSTEM_PROMPT + user question + aggregate tool outputs.
   ├──► LLM Provider Layer (backend/app/llm/)
   │      base.py (neutral types) -> factory.py -> gemini.py (google-genai SDK)
   │      (fake.py used in automated tests only; never env-selectable)
   ├──► Analysis Tool Registry (backend/app/agent/tools.py)
   │      Pydantic-validated tools wrapping backend/app/metrics/ and backend/app/findings/ ONLY.
   │      Persists tool_trace to AgentRun after EVERY tool call so polling shows live progress.
   └──► Deterministic Grounding Check (backend/app/agent/grounding.py)
          Verifies cited figures, call IDs, and causal-wording bans on every block
          without removing or mutating block text.
```

### Persistence & Startup Recovery
- Table `agent_runs` (`AgentRun` in `backend/app/models.py`) stores `id`, `engagement_id`, `dataset_id`, `question`, `status` (`running | completed | failed`), `answer_status` (`structured | unstructured | none`), `answer_blocks`, `tool_trace`, `warnings`, `error`, `model`, `round_trips`, `started_at`, `finished_at`, and `duration_ms`.
- Deleting an engagement cascades and deletes its `agent_runs`. Deleting a dataset retains historical `agent_runs` and keeps their `dataset_id` reference intact.
- On backend startup (`lifespan` in `backend/app/main.py`), any `AgentRun` still marked `running` is transitioned to `status="failed"` with error code `interrupted`.

---

## 2. Analysis Tools

All tools are bound server-side to the run's `engagement_id` and `dataset_id` via `ToolRunContext`. Tools **never accept** `dataset_id` or `engagement_id` arguments, and all argument models enforce `extra="forbid"`. Unknown tools and invalid arguments return `ok=false` with a structured `ToolError` (`code`, `message`) rather than raising exceptions. Table lists longer than **60 rows** are truncated with `truncated=true` and `original_row_count`.

| Tool | Arguments (Pydantic) | Underlying Metrics / Findings Wrapped |
| --- | --- | --- |
| `get_ticket_summary` | `volume_view`: `"none" \| "by_day" \| "by_hour" \| "by_band" \| "by_channel"` (default `"none"`) | Dataset metadata, `as_of`, scope summary & exclusions, the 6 Diagnostics KPIs (`first_response_time`, `triage_time`, `resolution_time`, `sla_attainment`, `backlog_ageing`, `reassignment_rate`), plus optional `volume_by_day` / `volume_by_hour` / `volume_by_band` / `volume_by_channel` |
| `get_response_metrics` | `metric`: `"first_response_time" \| "agent_response_time" \| "triage_time" \| "triage_share_of_first_response" \| "first_response_by_band" \| "sla_attainment" \| "factor_comparison"` | Exact corresponding `MetricResult` from `backend/app/metrics/` |
| `get_resolution_metrics` | `metric`: `"resolution_time"` (default `"resolution_time"`) | `resolution_time` `MetricResult` |
| `get_category_breakdown` | `view`: `"volume" \| "delay_table" \| "reassignment"` | `volume_by_category`, `category_delay_table`, or `reassignment_rate` |
| `get_agent_workload` | _(none)_ | `agent_workload` `MetricResult` (counts, top-3 share, unassigned, Gini) |
| `get_backlog_analysis` | _(none)_ | `backlog_ageing` `MetricResult` (open backlog total, oldest age days, ageing buckets) |
| `get_findings` | _(none)_ | Deterministic rule-based `findings` + combined `validation_questions` from `backend/app/findings/` |

> **Extensibility:** `ToolRegistry` registers declarative `ToolSpec` definitions so future triage tools (`classify_ticket`, `recommend_priority`, `draft_ticket_response`, `create_triage_proposal`, `record_human_decision`) can be attached without modifying `loop.py`.

---

## 3. Answer Block Schema

The agent's final response must be JSON matching:

```json
{
  "blocks": [
    {
      "type": "finding | hypothesis | recommended_next_step | clarifying_question | limitation",
      "text": "Concise text (1 to 600 characters).",
      "evidence_call_ids": ["c1"]
    }
  ]
}
```

- Maximum **8 blocks** per response; maximum **600 characters** per block.
- Markdown code fences around the JSON are stripped automatically.
- If the final response is malformed JSON or violates the schema, the loop sends **one** repair prompt (`tools=None`). If parsing still fails, the run completes with `answer_status="unstructured"` and keeps the raw text labelled `"Unverified response"` — never displayed as findings.

---

## 4. Grounding Rules & Tolerances

`check_grounding()` in `backend/app/agent/grounding.py` inspects every structured block deterministically and attaches non-destructive warnings (content is never silently removed):

1. **Precision-aware numeric matching:** A number shown with $d$ decimal places is grounded if any numeric value $v$ in the cited successful tool result(s) satisfies $|v - \text{shown}| \le 0.5 \times 10^{-d} + 10^{-9}$ (e.g., `6.07` grounds `6.07`, `6.1`, and `6`, while `6.2` or `7` is flagged).
2. **Percentages of fractions:** When a number is followed by `%` or `percent`, it also matches $v \times 100$ at the shown precision (e.g., `0.65` grounds `65%`).
3. **Counts and magnitudes:** Exact counts (including comma-formatted integers such as `1,971`) match directly.
4. **Ignored tokens:**
   - Integers `0`–`10` **without** an operational unit (`%`, `h`, `hour`, `hours`, `tickets`, `days`, `categories`, `agents`).
   - Dates (`YYYY-MM-DD`, `MM/DD/YYYY`, `Sep 7, 2026`), clock times (`18:00-22:00`), standalone 4-digit years (`1900`–`2099` without a unit), and identifier labels (`Agent 01`, `c1`, `F-01`, `p90`).
5. **Citation & causal checks on `finding` blocks:**
   - `unsupported_finding`: raised when a `finding` has no `evidence_call_ids` or cites a missing/failed tool call. (`hypothesis`, `recommended_next_step`, `clarifying_question`, and `limitation` blocks may have no citations.)
   - `causal_wording_in_finding`: raised when a `finding` uses any banned causal phrase: `because`, `caused`, `causes`, `due to`, `leads to`, `led to`, `result of`, `resulting from`, `drives`, `driven by`.
   - `number_only_in_uncited_call`: raised when a figure does not appear in the block's cited calls but appears in another successful call from the same run.
   - `ungrounded_number`: raised when a figure cannot be matched in any cited or uncited successful tool call from the run.

---

## 5. Limits & Error Codes

### Limits
- **Question length:** `1`–`1,000` characters.
- **Model round trips:** max `6` per investigation run (hitting the cap returns the partial trace plus a `"The investigation stopped at its limit..."` limitation block).
- **Tool calls:** max `10` per run (hitting the cap returns the partial trace plus a limitation block).
- **Overall run timeout:** `60` seconds.
- **Per-request provider timeout:** `LLM_TIMEOUT_SECONDS` (default `30` s).
- **Provider retries:** `LLM_MAX_RETRIES` (default `2`), exponential backoff on HTTP `429` and transient `5xx` only; never retries auth (`401`/`403`) or invalid-request (`400`) errors.
- **Output cap:** `LLM_MAX_OUTPUT_TOKENS` (default `1500`).
- **Table truncation:** `60` rows per tool result table.

### Error Codes
| Code | HTTP / Run Surface | Meaning |
| --- | --- | --- |
| `llm_not_configured` | `409 Conflict` on `POST` | `LLM_API_KEY` or `LLM_MODEL` missing/empty |
| `unsupported_provider` | `409 Conflict` on `POST` | `LLM_PROVIDER` not in supported providers (`gemini`) |
| `no_dataset` | `422 Unprocessable` on `POST` | Engagement has no uploaded or active dataset |
| `run_in_progress` | `409 Conflict` on `POST` | Another run is already `running` for this engagement |
| `llm_timeout` | Run `failed` | Provider request exceeded `LLM_TIMEOUT_SECONDS` |
| `llm_rate_limited` | Run `failed` | Provider returned HTTP `429` after exhausting retries |
| `llm_auth_error` | Run `failed` | Provider rejected credentials (`401`/`403`) |
| `llm_provider_error` | Run `failed` | Other upstream provider/network error |
| `overall_timeout` | Run `failed` | Total investigation exceeded `60` s |
| `interrupted` | Run `failed` (on startup) | Backend restarted while run was `running` |
| `unknown_tool` / `invalid_arguments` | Tool trace (`ok=false`) | Model called an unknown tool or failed Pydantic validation |

---

## 6. Privacy & Secret Hygiene

- **Outbound payload boundary:** Messages sent to the LLM provider contain **ONLY** the static `SYSTEM_PROMPT`, the user's question, and aggregate tool outputs (`MetricResult` summaries and rule-based findings). **No row-level ticket data** (`ticket_id`, `customer_id`, raw ticket rows), **no interview notes**, **no client statement**, and **no `data/answer_key.json`** are ever transmitted to the provider.
- **Secret scrubbing:** `LLM_API_KEY` is never exposed in `/api/health`, `AuditLog`, `AgentRun.error`, API responses, or logs. Error messages pass through `scrub_secrets()` before being persisted or returned.

---

## 7. Known Limitations

1. **Single-turn only:** Each investigation run is independent with no multi-turn conversational memory across runs.
2. **Single production provider adapter:** Only the `gemini` adapter (`google-genai`) is currently wired in `factory.py`; adding another provider requires implementing `LLMProvider` in `backend/app/llm/`.
3. **Grounding is not a semantic proof:** Deterministic grounding verifies that figures match cited tool outputs within precision tolerance and flags causal phrasing, but it cannot guarantee that a qualitative interpretation or causal hypothesis is operationally true — human review and client validation remain required.
