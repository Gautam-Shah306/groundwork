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
