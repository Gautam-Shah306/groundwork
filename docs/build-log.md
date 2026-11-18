# Groundwork Build Log

## Prompt 1 — Project Scaffold & Application Shell (2026-11-18)

### What was built
- **Documentation & Rules:** Renumbered `AGENTS.md` rules to R1–R12, added the Windows/PowerShell `Environment` section, created `docs/build-log.md`, updated `.env.example` with `CORS_ORIGINS`, and replaced `README.md` with native PowerShell, Docker, and test instructions.
- **Backend (`backend/`):** FastAPI application (`app/main.py`, `app/config.py`, `app/api/health.py`) with Pydantic Settings, CORS configured from environment variables, non-blocking startup when `LLM_API_KEY` is empty, `GET /api/health` returning `status`, `version`, `llm_configured`, and `database_url_scheme` only, and 6 pytest tests achieving 100.00% coverage (`>= 90%` gate).
- **Frontend (`frontend/`):** Vite 6 + React 19 + TypeScript + Tailwind CSS v4 (`4.3.5` with `@tailwindcss/vite`) + React Router 7 + Recharts + lucide-react + Vitest/Testing Library. Self-hosted `@fontsource/inter` and `@fontsource/instrument-serif`. Verbatim CSS tokens from section 15 of `docs/design-system.md` in `src/styles/tokens.css`, mapped into Tailwind v4 via `@theme inline` in `src/index.css`.
- **Application Shell & UI Kit:** Persistent 230px sidebar with Workspace and Stages route groups, 64px top bar with dynamic breadcrumbs and live `/api/health` status indicator, 6 route shells (`Overview`, `Engagements`, `Discovery`, `Diagnostics`, `Prototypes`, `Outcomes`), 8 shared UI components (`Button`, `Card`, `StatusPill`, `DataTable`, `KpiTile`, `TypeLabel`, `EmptyState`, `Eyebrow`), dev-only `/dev/components` gallery, and 12 Vitest + Testing Library tests.
- **Docker:** `backend/Dockerfile` (`python:3.11-slim`), `frontend/Dockerfile` (`node:22-slim`, using `npm ci` with `frontend/package-lock.json`), `.dockerignore` files, and `docker-compose.yml` running both services with `./data` mounted and `/api` proxied from frontend to backend.

### Decisions made
- **Native Python + Dockerized Node:** Python 3.11.9 was available natively, so backend venv and pytest run natively. Node/npm were absent on the host, so frontend install, Vitest, TypeScript check, Vite build, and dev server run in Docker (`node:22-slim`) without installing system software.
- **Tailwind CSS v4 (`4.3.5`) with `@theme inline`:** Kept `src/styles/tokens.css` 100% verbatim from section 15 of `docs/design-system.md` and mapped its CSS custom properties into Tailwind v4 using `@theme inline` to prevent cyclic CSS custom property declarations.
- **Switched `frontend/Dockerfile` from `node:22-alpine` to `node:22-slim`:** Resolved a Rollup 4.68.6 native parser error (`Code is nested too deeply` in `react-dom/client.js`) caused by Alpine musl's small thread stack size.
- **Route registration guard:** Parameterized `AppRoutes` with `isDev = import.meta.env.DEV` so `/dev/components` is excluded in production builds and deterministically tested in Vitest.

### Anything surprising
- Initial Part 0 verification stopped because `docs/project-brief.md` and `docs/design-system.md` were missing until added by the user.
- `node` and `npm` were not installed natively on the host; Docker Engine 29.6.1 and Python 3.11.9 were available.
- `vite build` failed on `node:22-alpine` with `[commonjs--resolver] Code is nested too deeply` in `node_modules/react-dom/client.js` (Rollup native parser on musl), and succeeded cleanly in `26.61s` after switching to `node:22-slim`.
- Native `uvicorn` launched via PowerShell `Start-Process` timed out waiting for `http://127.0.0.1:8000/api/health` in the agent shell (while direct `http://localhost:8000/api/health` and proxied `http://localhost:5173/api/health` both returned HTTP 200 in Docker Compose, and all 6 native `pytest` tests passed with 100% coverage).


## Prompt 2 — Persistence Layer, Engagement Management, Seed Data & Overview/Engagements Screens (2026-11-18)

### What was built
- **Backend Persistence (`backend/app/`):** Added SQLAlchemy 2.0 ORM table models in `app/models.py` for all 10 tables (`engagements`, `interview_notes`, `problem_briefs`, `datasets`, `tickets`, `triage_proposals`, `audit_logs`, `kpis`, `eval_runs`, `pilot_simulations`) with UTC timestamps (`UTCDateTime` TypeDecorator) and `PRAGMA foreign_keys=ON` cascading deletes in `app/db.py`.
- **Database Path Alignment:** Added `get_project_root()` and `resolve_database_url()` in `app/config.py` so the default `sqlite:///./data/groundwork.db` resolves to `<repo>/data/groundwork.db` natively (whether run from `backend/` or repo root) and to `/app/data/groundwork.db` inside Docker (bind-mounted to `./data`).
- **Pydantic Schemas & Endpoints:** Separate request/response schemas in `app/schemas.py` (no ORM objects returned directly); CRUD routes for `/api/engagements`, `/api/engagements/{id}/notes`, `/api/engagements/{id}/brief` (404 before first PUT, upsert on PUT), and `/api/engagements/{id}/activity?limit=10` (newest first); automatic `AuditLog` entries (`actor="Demo operator"`) on every create, update, and delete.
- **Idempotent Seed & Startup Hook:** Implemented `python -m app.seed` (`app/seed.py`) creating the fictional synthetic engagement `"Kora Living: Customer support turnaround"` (stage `discover`, `is_synthetic=True`, client statement from `docs/project-brief.md`) and a 473-word qualitative first-person intake interview transcript (`Operations lead intake interview — Maya Chen`) with zero numeric metric claims. Added `SEED_ON_START` env var (default `false`) in `app/config.py`, `.env.example`, and `docker-compose.yml`.
- **Frontend (`frontend/src/`):** Added `EngagementProvider` / `useEngagement` (`context/EngagementContext.tsx`) persisting active engagement selection in `localStorage` with delete fallback; new shared `SyntheticDataNotice` component (also added to `/dev/components`); dynamic active-engagement breadcrumbs in `TopBar`; full `EngagementsPage` (table, create form with field validation preserving inputs on error, select active, two-step delete confirmation, inline status banner, loading/empty/error states); full `OverviewPage` (date greeting, active engagement summary, problem statement or Discovery empty state, four-step stage progress with `aria-current="step"`, static stage-driven recommended next steps, newest-first recent activity feed, and `SyntheticDataNotice`).
- **Tests & Docs:** Added 19 backend tests (`tests/test_persistence.py`, total 25 backend tests at 94.37% coverage) and 13 frontend tests (`src/__tests__/EngagementsOverview.test.tsx`, total 25 frontend tests passing). Updated `AGENTS.md` Environment section with Docker frontend commands and added the `Database` section and `SEED_ON_START` docs to `README.md`.

### Decisions made
- **SQLAlchemy 2.0 + `create_all` (no migration tool):** Used SQLAlchemy 2.0 declarative models separate from Pydantic v2 schemas and `Base.metadata.create_all()` on startup via FastAPI `lifespan` to keep MVP persistence simple and deterministic without introducing Alembic overhead.
- **Preserving deletion audit records:** Operational child tables (`interview_notes`, `problem_briefs`, `datasets`, `tickets`, `triage_proposals`, `kpis`, `eval_runs`, `pilot_simulations`) use `ON DELETE CASCADE` on `engagements.id`, while `audit_logs` stores `engagement_id` as an indexed nullable integer without cascade delete so engagement deletion events remain auditable.
- **Shared SQLite resolution via repo-root detection:** `get_project_root()` detects when the package runs under `<repo>/backend` (with `docker-compose.yml` in the parent) vs `/app` in Docker, anchoring relative `sqlite:///./data/...` paths to the same `data/groundwork.db` file in both environments.

### Anything surprising
- Prompt 1's single backend test warning (`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`) originates inside `.venv\Lib\site-packages\fastapi\testclient.py:1` (upstream Starlette 1.10.0) and was left untouched and reported verbatim.
- PowerShell stripped double quotes inside inline `python -c '...'` arguments; using a single-quoted PowerShell here-string piped to `python -` avoided quoting issues cleanly.
- Under heavy container load immediately after `docker compose up -d --build`, one async Vitest `waitFor` timed out at the default 1s window; once the empty-state text alignment fix was applied, all 25/25 frontend tests passed cleanly in 28.69s.


## Prompt 3 — Synthetic Data Generator, Triage Config, Policies & Deterministic Priority Function (2026-11-18)

### What was built
- **Part 0 Audit-History Leak Fix:** Enabled `sqlite_autoincrement=True` on `Engagement.__table_args__` in `backend/app/models.py` so SQLite never reuses deleted engagement IDs, recreated `data/groundwork.db` and re-seeded cleanly, and added `test_new_engagement_does_not_inherit_deleted_engagement_audit_history`.
- **Dependencies & Docker Mounts:** Added `pandas`, `numpy`, and `pyyaml` to `backend/requirements.txt` and `backend/pyproject.toml`, added `resolved_config_dir` and `resolved_knowledge_dir` helpers on `Settings` in `backend/app/config.py`, and mounted `./config:/app/config:ro` and `./knowledge:/app/knowledge:ro` into the backend container in `docker-compose.yml`.
- **Triage Config & Deterministic Priority (`config/`, `backend/app/triage/`):**
  - Created `config/queues.yaml` (7 categories with display names mapped to 5 queues) and `config/priority_rules.yaml` (10 closed-vocabulary signals, 9 ordered rules `R-LEGAL` through `R-GENERAL`, default `R-DEFAULT:medium`).
  - Built Pydantic config validator (`app/triage/config.py`), pure deterministic `evaluate_priority()` (`app/triage/priority.py`, no LLM involvement per R1/R4), CLI check (`python -m app.triage.check`), and 16 unit tests (`backend/tests/test_triage_priority.py`).
- **Knowledge Base:** Created fictional Kora Living policies in `knowledge/policies.md` covering returns, damaged/wrong replacements, refund processing, payment reversals, delivery timelines, address changes, account lockouts, escalation rules, and bracketed-placeholder tone guidelines (R8).
- **Deterministic Synthetic Data Generator (`scripts/`):**
  - Created `scripts/eval_templates.py` (hand-written varied phrasings: >=8 English templates per category, 14 Hinglish, 17 English ambiguous + 2 Hinglish ambiguous = 19 ambiguous, 14 very short <12 words) and `scripts/generate_data.py` (fixed seed `42`, byte-identical SHA256 across runs).
  - Generated `data/sample_tickets.csv` (2,000 rows over 8 weeks in `+05:30` IST with planted bottlenecks and exact 12/3/8/6/9/4 injected quality issues), `data/eval_tickets.json` (150 unique tickets with `true_priority` verified against `evaluate_priority()`), and `data/answer_key.json` (for tests/docs only; verified unreferenced by `backend/app` per R6).
  - Added 19 tests in `backend/tests/test_data_generation.py` (total backend suite: 61 passed, 92.75% coverage).
- **Documentation:** Created `docs/data-dictionary.md`, added the `Synthetic Data` section to `README.md`, and added the Docker lockfile sync rule to `AGENTS.md`.

### Decisions made
- **Separate `scripts/eval_templates.py` data module:** Kept hand-written evaluation phrasings separate from generation logic in `scripts/generate_data.py` for readability and maintainability.
- **Disjoint quality-issue injection:** Applied each of the 6 injected anomalies (12 missing FRT, 3 duplicate IDs, 8 FRT-before-created, 6 `billing_misc`, 9 missing resolved_at, 4 >300-day resolved_at) to strictly non-overlapping rows so counts are exact and clean-row planted-effect analysis is unambiguous.
- **Exclusive `R-GENERAL` guard (`only_if_no_other_signals: true`):** Explicitly enforced in `priority_rules.yaml` and `evaluate_priority()` so `general_inquiry` paired with any other signal can never evaluate to `low`.

### Anything surprising
- Tuning lognormal parameters on seed `42` landed staffed triage lag at `3.43 h`, triage share of FRT at `63.6%` (within 55–65%), order+returns vs other reassignment at `33.3%` vs `8.8%` (3.78x), afternoon vs evening FRT at `4.79 h` vs `7.45 h`, and top-3 agent share at `40.0%` (`0.71 h` FRT delta vs `3.43 h` triage lag).
- `where.exe node` confirmed Node is not installed on the host, so all frontend checks ran cleanly in Docker (`25/25` Vitest tests, `0` TypeScript errors).


## Prompt 4 — CSV Upload, Validation Pipeline & Diagnostics Data Screen (2026-11-18)

### What was built
- **Part 0 `Ticket` Surrogate Key Fix:** Updated `Ticket` in `backend/app/models.py` to use a surrogate autoincrement integer primary key (`row_id`, `sqlite_autoincrement=True`) with `ticket_id` as a plain indexed non-unique string column (and added `is_sample` to `Dataset`). Recreated `data/groundwork.db`, re-seeded via `python -m app.seed`, added `test_ticket_model_allows_duplicate_ticket_ids_and_same_ids_across_engagements`, and added `resolved_data_dir` on `Settings` (`get_project_root() / "data"`) so `data/sample_tickets.csv` resolves identically natively and via Docker's `./data:/app/data` mount.
- **Backend Ingestion & Validation (`backend/app/ingest/`, `backend/app/api/datasets.py`):**
  - Built pure CSV parser (`parse.py`: `.csv` extension check, 10 MB / 50,000-row limits, `utf-8-sig` BOM handling, `pandas.read_csv(..., dtype=str, keep_default_na=False)`, exact 13 required columns, extra-column warning, cell trimming, lowercasing of vocabulary fields while preserving ID case, plain-text retention of formula-prefix cells `= + - @`).
  - Built deterministic validator (`validate.py`: UTC timestamp storage with `Asia/Kolkata` fallback + `timestamps_without_timezone` warning, exact 14 check codes with scope flags `all_metrics`, `response_metrics`, `resolution_metrics`, `triage_metrics`, `IMPLAUSIBLE_DURATION_DAYS = 180`, no rows dropped).
  - Built atomic transactional service (`service.py`) storing `Dataset`, all `Ticket` rows (populating real `row_id` example references), and `AuditLog` entries; added `POST /datasets`, `POST /datasets/sample`, `GET /datasets`, `GET /datasets/{dataset_id}`, `GET /datasets/{dataset_id}/rows`, and `DELETE /datasets/{dataset_id}` endpoints.
  - Added `python-multipart` to `backend/requirements.txt` and `backend/pyproject.toml`, and added 31 ingestion tests (`backend/tests/test_ingest.py`; total 93 backend tests passing at 93.64% coverage).
- **Frontend Diagnostics Data Screen (`frontend/src/pages/DiagnosticsPage.tsx`):**
  - Implemented engagement empty state, keyboard-operable CSV dropzone (`Enter`/`Space`) with 10 MB / 50,000-row limits and required-columns reference, `"Load sample dataset"` action with `SyntheticDataNotice`, upload progress phases (`Uploading`, `Validating`, `Saving`) with indeterminate progressbar and live region, error state retaining filename + retry, dataset overview & switcher, confirmation-gated delete, `Observed fact` validation summary with plain-language per-scope exclusion statement, passed-checks toggle, expandable inline row examples, and paginated row drill-down (plain text rendering only — never HTML).
  - Added 14 Vitest tests in `frontend/src/__tests__/Diagnostics.test.tsx` (total 39 frontend tests passing).
- **Documentation:** Added Section 6 (`Validation Pipeline & Rules`) to `docs/data-dictionary.md` and `Uploading Data` to `README.md`.

### Decisions made
- **Prompt 3 data-shaping note:** Recorded that the staffed-hours median agent response lag in `scripts/generate_data.py` is about 1.9 h (not the ~1 h first specified) so that triage lag is about 64% of first-response time.
- **Scoping `assignment_order_inconsistent`:** Checked `assigned_at > first_response_at` only when `first_response_at >= created_at`, preventing rows with corrupt `first_response_before_created` timestamps from spuriously contaminating `triage_metrics`.
- **Single-transaction `row_id` example references:** Flushed `Ticket` inserts inside the upload transaction before finalizing `Dataset.validation_report` so up-to-5 example rows per check reference real database `row_id`s while preserving full rollback on any failure.

### Anything surprising
- Placing the hidden `<input type="file" />` inside the dropzone's `<div onClick={...}>` caused `fileInput.click()` to bubble back up and fire twice on keyboard `Enter`/`Space` — caught immediately by the keyboard-operability test and fixed by moving the hidden input outside the clickable dropzone container.
- Starlette `1.10.0` deprecated `HTTP_422_UNPROCESSABLE_ENTITY` in favor of `HTTP_422_UNPROCESSABLE_CONTENT`; updated `backend/app/api/datasets.py` so no warnings originate from our own code.
