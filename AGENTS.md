# Groundwork: agent rules

## Product
Groundwork is a business operations intelligence workspace. An operator takes a
client's vague problem through four stages: Discover, Diagnose, Build, Measure.
Read docs/project-brief.md for product intent and docs/design-system.md for UI.
Initial scenario: customer-support operations for a FICTIONAL e-commerce
company ("Kora Living"). All data is synthetic and must be labelled as such.

## Stack
- Frontend: React + Vite + TypeScript, Tailwind CSS, React Router, Recharts.
- Backend: Python 3.11+, FastAPI, Pydantic, SQLite (SQLModel or SQLAlchemy),
  Pandas, NumPy. pytest for tests.
- Docker Compose runs both. Config via environment variables (.env, never committed).
- Layout: /frontend, /backend, /data, /scripts, /docs, /knowledge, /config.

## Non-negotiable rules
1. The LLM NEVER calculates, estimates or invents business metrics. All numbers
   come from deterministic, unit-tested Python functions in backend/metrics/.
2. Every agent finding must reference the tool call(s) that produced its figures.
3. No customer-facing message is ever sent. The agent proposes; a human
   approves, edits or rejects; every decision is written to the audit log.
4. Separate business logic from AI orchestration (backend/metrics vs backend/agent).
5. Agent tools validate arguments with Pydantic and return structured errors.
6. data/answer_key.json is for tests and the generator only. The app must never
   read it or expose it to the LLM.
7. Simulated or synthetic results must be visibly labelled "Simulated result" /
   "Synthetic data" wherever they appear.
8. Draft replies use only knowledge/policies.md and ticket content. Unknown
   facts become bracketed placeholders, never invented details.

## UI rules
- Follow docs/design-system.md exactly: tokens, Inter + Instrument Serif,
  light theme only, fine borders, minimal shadows, no gradients.
- Always distinguish: Observed fact, Client statement, Hypothesis,
  AI recommendation, Approved action, Measured outcome, Simulated result
  (use a shared <TypeLabel> component).
- Every screen needs loading, empty, error and success states.
- Use a shared set of components (Button, Card, StatusPill, DataTable,
  KpiTile, TypeLabel, EmptyState, Eyebrow). Do not restyle per page.

## Process
- Work on the milestone I give you; do not build ahead.
- Write pytest tests for every metrics function and every tool.
- Do not run git commit, git push or change git config. I commit manually.
- When done, summarise what you built, how to run it, and what you did NOT do.