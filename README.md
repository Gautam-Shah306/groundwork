# Groundwork

Groundwork is an AI-assisted business operations intelligence workspace that guides an operator from an unstructured client problem through four connected stages: Discover, Diagnose, Build, and Measure. The initial scenario models customer-support operations for a fictional e-commerce company ("Kora Living"), and **all data used in the workspace is synthetic and explicitly labelled as such**; deterministic Python functions compute all metrics, and every agent-proposed action requires human approval and audit logging.

## Prerequisites

- **Python 3.11+** (for native backend execution)
- **Node.js 20+ and npm** (for native frontend execution), **or Docker Desktop / Docker Engine with Docker Compose** (if running the frontend or full stack in containers)
- Copy `.env.example` to `.env` if you want to customize environment variables (`.env` is gitignored; the app starts cleanly with an empty `LLM_API_KEY`).

## Run Natively (Windows PowerShell)

### Backend

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
Pop-Location
```

Verify the backend health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

### Frontend (requires Node 20+)

```powershell
Push-Location frontend
npm ci
npm run dev
Pop-Location
```

The frontend runs on `http://localhost:5173` and proxies `/api` requests to `http://localhost:8000` (configurable via `VITE_API_PROXY_TARGET` or `VITE_API_BASE_URL`).

## Run with Docker

```powershell
docker compose build
docker compose up -d
```

- Frontend shell: `http://localhost:5173`
- Proxied backend health check: `http://localhost:5173/api/health`
- Direct backend API: `http://localhost:8000/api/health`

Stop and remove containers:

```powershell
docker compose down
```

## Database

- **SQLite file location:** `data/groundwork.db` at the repository root (git-ignored via `*.db`). Relative `DATABASE_URL` values such as the default `sqlite:///./data/groundwork.db` are anchored to the repository root natively (`backend/` cwd) and to `/app/data/groundwork.db` in Docker (bind-mounted to `./data`), so both environments share the same database file.
- **Seed synthetic demo data (idempotent):**
  ```powershell
  Push-Location backend
  .\.venv\Scripts\python.exe -m app.seed
  Pop-Location
  ```
- **Auto-seed on startup:** Set `SEED_ON_START=true` in `.env` (defaults to `false`) to run the idempotent Kora Living seed automatically when the backend starts.
- **Reset the database:** Stop the backend / Docker containers, remove `data/groundwork.db`, and re-run the seed command:
  ```powershell
  Remove-Item data\groundwork.db -ErrorAction SilentlyContinue
  ```

## Synthetic Data

All operational tickets, evaluation tickets, policies, and ground-truth references belong to the **fictional** company **Kora Living** and are deterministically generated with fixed seed `42` (identical output bytes on every run).

- **Generated files (in `data/`):**
  - `data/sample_tickets.csv` — 2,000 synthetic support tickets over 8 weeks (`+05:30` IST) with planted operational bottlenecks and exact injected data-quality anomalies.
  - `data/eval_tickets.json` — 150 varied synthetic triage evaluation tickets (English, Hinglish, ambiguous, short, urgent/delayed).
  - `data/answer_key.json` — planted-cause reference for tests and documentation only (never read by `backend/app`, per `R6`).
- **Configuration and policy files:** `config/queues.yaml`, `config/priority_rules.yaml`, and fictional `knowledge/policies.md`.
- **Regenerate synthetic datasets (PowerShell, native Python 3.11 venv):**
  ```powershell
  backend\.venv\Scripts\python.exe scripts\generate_data.py
  ```
- **Verify triage configuration:**
  ```powershell
  Push-Location backend
  .\.venv\Scripts\python.exe -m app.triage.check
  Pop-Location
  ```
  See [`docs/data-dictionary.md`](./docs/data-dictionary.md) for the complete schema and vocabularies.

## Discovery Workspace

The **Discovery** workspace transforms qualitative stakeholder interview notes into a structured, testable problem brief (see [`docs/discovery.md`](./docs/discovery.md)).

- **Interview Notes:** Add and manage interview notes with automatic word counts and character tracking.
- **AI-Assisted Analysis:** Select one or more notes (up to 30,000 characters) and run `POST /api/engagements/{id}/discovery/analyse` to extract themes, symptoms, impacts, hypotheses, known facts, and candidate KPIs.
- **Deterministic Post-Processing:** Verifies source quotes against notes text, validates number claims, checks hypothesis hedging, bans causal language in problem statements, and restricts candidate KPIs to the 16 approved metrics in the Groundwork metrics registry.
- **Version History & Safeguards:** Maintains up to 5 version snapshots per engagement. Applying an AI draft over manually edited briefs requires explicit confirmation (`confirm_replace: true`).
- **Discovery Token Limit (`LLM_DISCOVERY_MAX_OUTPUT_TOKENS`):** Default `4000` tokens to support full structured brief generation across all 13 sections.

## Uploading Data

1. Open **Diagnostics** in the workspace sidebar (with an engagement selected).
2. Upload any `.csv` ticket export matching the 13 required columns (up to **10 MB** / **50,000 rows**, UTF-8 or UTF-8 with BOM), **or** click **Load sample dataset** to run `data/sample_tickets.csv` through the exact same validation pipeline.
3. Invalid rows are never dropped — every row is stored with deterministic flags (`all_metrics`, `response_metrics`, `resolution_metrics`, `triage_metrics`) and inspectable via the per-check row drill-down.
4. Equivalent API endpoints:
   - `POST /api/engagements/{id}/datasets` (multipart `.csv` file upload)
   - `POST /api/engagements/{id}/datasets/sample` (loads `data/sample_tickets.csv`)
   - `GET /api/engagements/{id}/datasets` and `GET /api/engagements/{id}/datasets/{dataset_id}/rows?flag=<code>&page=1&page_size=25`
   - `DELETE /api/engagements/{id}/datasets/{dataset_id}`

## Metrics and Findings

All operational KPIs, distribution metrics, factor comparisons, and rule-based findings are computed deterministically from stored SQLite ticket rows via `GET /api/engagements/{id}/datasets/{dataset_id}/diagnostics` (read-only, configured in `config/metrics.yaml`). See [`docs/metrics.md`](./docs/metrics.md) for exact formulas, scopes, right-censoring caveats, illustrative SLA thresholds, and finding rules.

## Assistant

Groundwork includes a contextual **Investigation assistant** on the Diagnostics page backed by deterministic analysis tools and numeric grounding checks (see [`docs/agent.md`](./docs/agent.md)).

- **Provider choice (`LLM_PROVIDER`):** Supports `gemini` (Google Gemini) and `groq` (Groq API).
- **Gemini setup:** Create an API key in Google AI Studio and configure `LLM_PROVIDER=gemini` and `LLM_MODEL=gemini-2.5-flash` in `.env`.
- **Groq setup:** Create an API key in the Groq Console and configure `LLM_PROVIDER=groq` and `LLM_MODEL=openai/gpt-oss-20b` (or `llama-3.3-70b-versatile`) in `.env`.
- **Free-tier limits:** Groq free-tier keys enforce strict tokens-per-minute (TPM), requests-per-minute (RPM), and tokens-per-day (TPD) limits. When testing or running investigations on free-tier keys, pause 15–20 seconds between queries to avoid short-window rate limits. If a per-day limit is reached, Groundwork surfaces `llm_quota_exhausted` and offers retry once the daily quota resets.
- **Local configuration (`.env`):** Copy `.env.example` to `.env` and populate:
  - `LLM_PROVIDER=gemini` or `LLM_PROVIDER=groq`
  - `LLM_API_KEY=` _(your private key)_
  - `LLM_MODEL=` _(required; no built-in default, e.g. `openai/gpt-oss-20b` or `gemini-2.5-flash`)_
  - Optional tuning defaults: `LLM_TIMEOUT_SECONDS=30`, `LLM_MAX_RETRIES=2`, `LLM_MAX_OUTPUT_TOKENS=2500`, `LLM_REASONING_EFFORT=low`
- **Never commit `.env` or your API key:** `.env` is git-ignored; never paste keys into docs, commits, issues, or logs.
- **Behaviour without a key:** Groundwork starts and runs normally with `LLM_API_KEY` or `LLM_MODEL` unset. `/api/health` reports `llm_configured: false` (without exposing keys or model names), all deterministic Diagnostics screens work normally, and the Assistant panel displays setup guidance with input disabled.

## Run Tests

### Backend (pytest + coverage gate >= 90%)

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-fail-under=90
Pop-Location
```

### Frontend (Vitest, TypeScript check, production build)

Natively (with Node 20+):

```powershell
Push-Location frontend
npm run test
npm run typecheck
npm run build
Pop-Location
```

Via Docker (with Compose running, when Node is not installed natively):

```powershell
docker compose exec -T frontend npm run test
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run build
```

## Documentation

- [Agent rules (`AGENTS.md`)](./AGENTS.md)
- [Project documentation (`docs/`)](./docs/)
  - [Project brief (`docs/project-brief.md`)](./docs/project-brief.md)
  - [UI/UX design system (`docs/design-system.md`)](./docs/design-system.md)
  - [Build log (`docs/build-log.md`)](./docs/build-log.md)
