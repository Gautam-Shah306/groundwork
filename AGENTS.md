# Groundwork: agent rules

## Product
Groundwork is a business operations intelligence workspace. An operator takes a
client's vague problem through four stages: Discover, Diagnose, Build, Measure.
Read `docs/project-brief.md` for product intent and `docs/design-system.md` for UI.
Initial scenario: customer-support operations for a FICTIONAL e-commerce
company ("Kora Living"). All data is synthetic and must be labelled as such.

## Stack
- Frontend: React + Vite + TypeScript, Tailwind CSS, React Router, Recharts.
- Backend: Python 3.11+, FastAPI, Pydantic, SQLite (SQLModel or SQLAlchemy),
  Pandas, NumPy. pytest for tests.
- Docker Compose runs both. Config via environment variables (`.env`, never committed).
- Layout: `/frontend`, `/backend`, `/data`, `/scripts`, `/docs`, `/knowledge`, `/config`.

## Environment
- Host OS and shell: Windows with PowerShell.
- Detect the installed toolchain first (`node --version`, `npm --version`,
  `python --version`, `docker --version`).
- Run Node natively if Node >= 20 and Python natively if Python >= 3.11;
  otherwise run that part in Docker. Do not install system software.
- PowerShell command hygiene: no double quotes inside native-command arguments,
  and use PowerShell-safe syntax (no `&&` chaining).
- Concrete frontend command pattern on this machine (when Node is not installed
  natively, with Compose running):
  - `docker compose exec -T frontend npm run test`
  - `docker compose exec -T frontend npx tsc --noEmit`
  - `docker compose exec -T frontend npm run build`
- Lockfile sync rule: whenever a frontend dependency is added or changed inside
  Docker, copy the updated `package-lock.json` back to the host
  (`docker compose cp frontend:/app/package-lock.json frontend/package-lock.json`)
  and confirm it appears in `git status`. Do not run git commands that modify
  history.

## Non-negotiable rules
- **R1.** The LLM NEVER calculates, estimates or invents business metrics. All numbers
  come from deterministic, unit-tested Python functions in `backend/metrics/`.
- **R2.** Every agent finding must reference the tool call(s) that produced its figures.
- **R3.** No customer-facing message is ever sent. The agent proposes; a human
  approves, edits or rejects; every decision is written to the audit log.
- **R4.** Separate business logic from AI orchestration (`backend/metrics` vs `backend/agent`).
- **R5.** Agent tools validate arguments with Pydantic and return structured errors.
- **R6.** `data/answer_key.json` is for tests and the generator only. The app must never
  read it or expose it to the LLM.
- **R7.** Simulated or synthetic results must be visibly labelled "Simulated result" /
  "Synthetic data" wherever they appear.
- **R8.** Draft replies use only `knowledge/policies.md` and ticket content. Unknown
  facts become bracketed placeholders, never invented details.

## UI rules
- **R9.** Follow `docs/design-system.md` exactly: tokens, Inter + Instrument Serif,
  light theme only, fine borders, minimal shadows, no gradients. Use a shared
  set of components (`Button`, `Card`, `StatusPill`, `DataTable`, `KpiTile`,
  `TypeLabel`, `EmptyState`, `Eyebrow`) and do not restyle per page. Always
  distinguish `Observed fact`, `Client statement`, `Hypothesis`,
  `AI recommendation`, `Approved action`, `Measured outcome`, and
  `Simulated result` using the shared `<TypeLabel>` component.
- **R10.** Every screen needs loading, empty, error and success states.

## Process
- **R11.** Write pytest tests for every metrics function and every tool; mock
  the LLM in tests.
- **R12.** Never stage, commit, push or change git config (the user commits manually).
  Work only on the prompt's scope; do not build ahead. Documentation edits ride
  in the same prompt as the code. Append an entry to `docs/build-log.md` for
  each prompt, and summarise what was built, how to run it, and what was not done.
