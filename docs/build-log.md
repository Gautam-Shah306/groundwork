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
