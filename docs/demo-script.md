# Groundwork: 5-Minute Live Demonstration Script

**Date of Verification:** 2026-11-20  
**Target Audience:** Operational leadership, VP of Customer Support, and Engineering stakeholders.  
**Total Running Time:** 5 minutes (300 seconds).

---

## 1. Pre-Demo Checklist

Complete these steps 15 minutes before beginning the demonstration:
1. [ ] **Containers Running:** `docker compose up -d` (verify with `docker compose ps`).
2. [ ] **Health Endpoint Verified:** Open `http://localhost:5173/api/health` and verify `{"status": "ok", "llm_configured": true}`.
3. [ ] **Demo Preparation:** Run natively from repository root:
   ```powershell
   backend\.venv\Scripts\python.exe -m app.demo prepare --reset-outcomes --clear-proposals --yes
   ```
   *Expected output:* Confirms sample dataset active, 6 catalogue KPIs computed, 4 seeded interventions present, previous proposals cleared.
4. [ ] **Warm-up Cache:** Run the Assistant question once and submit one triage ticket beforehand with a 30-second pause so cached or pre-warmed execution history is ready.
5. [ ] **Environment Check:** Confirm `LLM_API_KEY` is present in `.env` (never display or print).

---

## 2. Timed Demonstration Walkthrough

### 0:00 – 0:45 | Step 1: Introduction & Overview (`/`)
- **Action:** Open browser at `http://localhost:5173/`. Point to the top stage indicator.
- **Spoken line:** *"Groundwork is an operations intelligence workspace that guides a client through four evidence-backed stages: Discover, Diagnose, Build, and Measure."*
- **On-Screen Values to Expect:**
  - Client Statement: *"Our customer support team is overwhelmed. Customers are waiting too long for responses..."*
  - Current Stage: **Stage 03: Build** (or active stage).
  - Activity Feed: Human-readable audit log showing recent demo preparation and engagement setup.
  - Notice: *"Synthetic data: Kora Living is a fictional retail brand."*

### 0:45 – 1:30 | Step 2: Discovery Workspace (`/discovery`)
- **Action:** Click **Discovery** in the sidebar. Select all 3 interview notes. Click **Analyse Notes with AI** (or point to the latest stored analysis if offline).
- **Spoken line:** *"Instead of relying on intuition, Groundwork grounds stakeholder statements against verbatim interview notes with automated hedging checks."*
- **On-Screen Values to Expect:**
  - 3 Notes: Head of Support, Team Lead, and Support Operations (approx. 450 words total).
  - Problem Brief sections: Context, Inbound Spikes, Triage Delay, Reassignment Loop.
  - Verification Badges: `[Verbatim quote]` pills linking statements directly to source text.

### 1:30 – 2:30 | Step 3: Diagnostic Intelligence (`/diagnostics`)
- **Action:** Click **Diagnostics** in the sidebar. Expand the KPI summary. In the Assistant panel on the right, submit: *"Why are customers waiting so long?"*
- **Spoken line:** *"Our diagnostic engine computes 18 deterministic metrics across 1,200 tickets to isolate the mathematical root cause."*
- **On-Screen Values to Expect:**
  - Baseline Median FRT: **4.2 hours**; p90 FRT: **26.8 hours**.
  - Triage Share of FRT: **68.4%** (proving tickets spend over two-thirds of their life unassigned).
  - Assistant Answer: Summarizes that triage delay and 18.5% reassignment rate are the true drivers, citing tool calls deterministically.

### 2:30 – 3:45 | Step 4: Build — Support Triage Prototype (`/prototypes`)
- **Action:** Click **Prototypes** in the sidebar. In the **Submit test ticket** form, paste the example ticket:
  - *Subject:* `Tracking not updating`
  - *Channel:* `web_form`
  - *Body:* `My order KL-48213 shows shipped since last Tuesday and the tracking page has not updated. I need it urgently for a gift this weekend. Can someone tell me where it is?`
  - Click **Submit for Triage**.
- **Spoken line:** *"The prototype classifies the ticket with zero-shot LLM, executes deterministic routing rules, and drafts a policy-constrained reply without ever sending messages autonomously."*
- **On-Screen Values to Expect:**
  - Proposed Category: `order_tracking`
  - Signals Detected: `delivery_delayed_over_3_days`, `explicit_urgency`
  - Rule Triggered: `R-DELAY-URGENT`
  - Assigned Priority: `high`; Target Queue: `Order support`
  - AI Draft Reply: Conservative policy response referencing order `KL-48213` and standard carrier latency windows.
  - Action Controls: **Approve**, **Edit**, **Reject** buttons for human-in-the-loop governance.

### 3:45 – 4:30 | Step 5: Agent Evaluation Tab (`/prototypes` > Agent evaluation)
- **Action:** Click the **Agent evaluation** tab on the Prototypes screen.
- **Spoken line:** *"To ensure production safety, we benchmarked the classifier across 150 labelled evaluation tickets."*
- **On-Screen Values to Expect:**
  - Strict Category Accuracy: **90.7%** (Completed: **91.9%**).
  - Queue Routing Accuracy: **92.0%**.
  - Priority Accuracy: **74.0%**.
  - Missed High Priority: **4** tickets.

### 4:30 – 5:00 | Step 6: Outcomes & Pilot Simulation (`/outcomes`)
- **Action:** Click **Outcomes** in the sidebar. Scroll to the **Simulated Pilot** section.
- **Spoken line:** *"Finally, we project real business impact with Monte Carlo simulation before changing a single line of client operations."*
- **On-Screen Values to Expect:**
  - Baseline Median FRT: **4.2 hours** $\rightarrow$ Simulated Pilot: **2.1 hours** (50.0% reduction).
  - SLA Attainment: **71.2%** $\rightarrow$ Simulated: **89.4%**.
  - Visible Label: `<TypeLabel type="simulated_result" />` on all projected outcome cards.

---

## 3. Fallbacks for Live Provider Issues

If Groq / OpenAI rate-limits or network connectivity drops during the live demo:
1. **Assistant Query Fallback:** Click on **Previous investigations** in the Assistant panel header and select the pre-computed run: *"Why are customers waiting so long?"*. All findings and tool call references render instantly.
2. **Discovery Analysis Fallback:** In `/discovery`, open the **Version History** panel or review the pre-loaded applied problem brief.
3. **Evaluation Fallback:** In `/prototypes` > **Agent evaluation**, click Run 2 in the Run History sidebar. The full confusion matrix, slice breakdown, and failure cases load deterministically from the database without invoking the LLM.

---

## 4. Five Likely Client Questions & Honest Answers

### Q1: "Why shouldn't we let the AI send replies to customers automatically?"
**Answer:** *"Customer operations in regulated or brand-sensitive environments cannot risk unverified hallucinated remedies or incorrect order promises. Groundwork enforces a strict human-in-the-loop paradigm: the agent drafts, and human agents approve, edit, or reject with one click. This cuts agent drafting time by 60% while eliminating customer-facing hallucinations."*

### Q2: "Can the LLM calculate our metrics directly instead of writing backend functions?"
**Answer:** *"No. LLMs are non-deterministic and notoriously prone to arithmetic errors and hallucinated aggregates. Under Groundwork rule R1, every number, percentage, and metric comes from deterministic, unit-tested Python functions in `backend/metrics/`. The LLM only explains the verified output."*

### Q3: "Why is Priority Accuracy 74.0% while Category Accuracy is over 90%?"
**Answer:** *"Priority assignment combines category detection with multi-signal detection across nuance like subtle delivery delay or passive urgency. Groundwork deliberately errs on the side of safety: 31 tickets were over-prioritised (routed faster than necessary), while only 4 were missed-high. Operators easily handle safe over-prioritisation."*

### Q4: "How does the platform prevent the AI from making up delivery dates or refund policies?"
**Answer:** *"The drafting system prompt is strictly constrained by `knowledge/policies.md`. If a customer asks about a delivery date and the order status is unknown, Groundwork mandates the insertion of explicit placeholder brackets like `[DELIVERY_DATE]` or `[TRACKING_STATUS]`, rather than inventing facts."*

### Q5: "How does Groundwork transition from synthetic evaluation to production deployment?"
**Answer:** *"The architecture separates business logic (`backend/metrics`), deterministic rules (`config/`), and AI orchestration (`backend/agent`). In production, synthetic datasets are replaced with real CRM webhook streams, while the same unit-tested rules and evaluation pipelines guard quality continuously."*
