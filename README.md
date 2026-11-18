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
npm install
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
npx tsc --noEmit
npm run build
Pop-Location
```

Via Docker (when Node is not installed natively):

```powershell
docker compose run --rm frontend npm run test
docker compose run --rm frontend npx tsc --noEmit
docker compose run --rm frontend npm run build
```

## Documentation

- [Agent rules (`AGENTS.md`)](./AGENTS.md)
- [Project documentation (`docs/`)](./docs/)
  - [Project brief (`docs/project-brief.md`)](./docs/project-brief.md)
  - [UI/UX design system (`docs/design-system.md`)](./docs/design-system.md)
  - [Build log (`docs/build-log.md`)](./docs/build-log.md)

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
npm install
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
npx tsc --noEmit
npm run build
Pop-Location
```

Via Docker (when Node is not installed natively):

```powershell
docker compose run --rm frontend npm run test
docker compose run --rm frontend npx tsc --noEmit
docker compose run --rm frontend npm run build
```

## Documentation

- [Agent rules (`AGENTS.md`)](./AGENTS.md)
- [Project documentation (`docs/`)](./docs/)
  - [Project brief (`docs/project-brief.md`)](./docs/project-brief.md)
  - [UI/UX design system (`docs/design-system.md`)](./docs/design-system.md)
  - [Build log (`docs/build-log.md`)](./docs/build-log.md)
