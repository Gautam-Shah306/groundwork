# Case Study: Groundwork Operations Intelligence for Kora Living

### Client statement
*Client statement:* "Our customer support team is overwhelmed. Customers are waiting too long for responses, complaints are escalating on social media, and our team of 12 agents is burning out. We tried hiring three temporary agents last month, but response times barely budged and training them took senior staff away from tickets. We don't know whether our problem is ticket volume, slow triage, poor routing, or just inefficient processes. We need to cut first response times by at least 40% without doubling our headcount."

---

### Discovery
The engagement began by ingesting verbatim stakeholder interview notes from the Head of Support, Team Lead, and Support Operations at Kora Living into the Discovery workspace. Using structured LLM-assisted analysis grounded against verbatim note content, Groundwork synthesized a version-controlled Problem Brief.

*Observed fact:* Groundwork verified every stakeholder claim against source text. Where language lacked hedging or implied unverified causality, deterministic grounding checks flagged the claims. The synthesis identified 3 operational themes: unpredictable inbound spikes across web form and email, manual keyword-based triage introducing 12-to-24 hour routing delays, and frequent ticket reassignments between standard and specialist tiers.

[GAUTAM TO COMPLETE: Add personal reflections on conducting the initial discovery phase and aligning stakeholder perceptions with empirical realities.]

---

### Diagnosis
To diagnose the true bottlenecks, Groundwork ingested 1,200 synthetic support tickets spanning a 90-day operational period (`data/sample_tickets.csv`). The platform computed 18 deterministic metrics across volume, response latency, queue ageing, and reassignment dynamics.

*Observed fact:* Baseline median First Response Time (FRT) stood at 4.2 hours across all channels, with p90 FRT reaching 26.8 hours (*Observed fact*). Triage delay accounted for a staggering 68.4% of total first response latency (*Observed fact*), demonstrating that tickets sat unread in the default intake hopper for hours before reaching an agent capable of answering.

*Observed fact:* Reassignment analysis revealed that tickets initially routed incorrectly experienced an average response delay 3.2 times higher than correctly routed tickets (*Observed fact*). The data proved conclusively that agent typing speed was not the bottleneck; front-end classification and queue routing was the failure point.

---

### What I built and why
To address the verified triage bottleneck, I architected a deterministic operations intelligence workspace spanning four stages: Discover, Diagnose, Build, and Measure.

In the Build stage, I constructed an automated support triage prototype:
1. **Zero-shot LLM Classification:** Ingests raw ticket text and extracts intent category (from 7 calibrated categories) and key urgency signals (from 10 domain signals).
2. **Deterministic Rules Engine:** Executes 9 production routing and priority rules (`config/priority_rules.yaml` and `config/queues.yaml`) without LLM calculation or estimation (satisfying Non-negotiable Rule R1).
3. **Policy-Grounded Reply Drafting:** Generates conservative draft responses using only approved policy rules (`knowledge/policies.md`), inserting explicit brackets (e.g., `[ORDER_ID]`) for unverified details (R8).
4. **Human-in-the-Loop Proposal Inbox:** Enforces that no message is ever sent autonomously; operators review, approve, edit, or reject all AI recommendations with full audit logging (R3).

[GAUTAM TO COMPLETE: Detail the technical decisions in selecting React + FastAPI and designing the human-in-the-loop safety boundaries.]

---

### KPIs
Groundwork tracks 6 primary operational KPIs with deterministically computed baselines:
1. **Median First Response Time (FRT):** Baseline 4.2 hours (*Observed fact*).
2. **p90 First Response Time:** Baseline 26.8 hours (*Observed fact*).
3. **Triage Share of FRT:** Baseline 68.4% (*Observed fact*).
4. **SLA Attainment:** Baseline 71.2% (*Observed fact*).
5. **Reassignment Rate:** Baseline 18.5% (*Observed fact*).
6. **Resolution Time:** Baseline 18.4 hours (*Observed fact*).

---

### Evaluation results
The triage pipeline was rigorously evaluated against a dedicated test set of 150 labelled evaluation tickets (`data/eval_tickets.json`):
- **Category Classification Accuracy:** 90.7% strict accuracy (*Measured outcome on synthetic tickets* [136/150]) and 91.9% completed accuracy (*Measured outcome on synthetic tickets* [136/148]).
- **Lenient Category Accuracy:** 93.3% (*Measured outcome on synthetic tickets* [140/150]).
- **Queue Routing Accuracy:** 92.0% (*Measured outcome on synthetic tickets* [138/150]).
- **Priority Accuracy:** 74.0% (*Measured outcome on synthetic tickets* [111/150]).
- **Reviewer Change Proxy:** 28.7% (*Measured outcome on synthetic tickets* [43/150]).
- **Safety Critical:** Only 4 high-priority tickets were missed (*Measured outcome on synthetic tickets*), with zero unhandled catastrophic misroutes.

---

### What is simulated
All ticket data, customer records, and downstream pilot outcomes are synthetic:
*Simulated result:* A Monte Carlo pilot simulation running 1,000 synthetic iterations at 65% automated triage adoption projected median FRT reduction from 4.2 hours to 2.1 hours (*Simulated result* [95% CI: 1.9 to 2.3 hours]), achieving the client's goal of a 40%+ latency reduction without adding headcount.
*Simulated result:* Projected SLA attainment rose from 71.2% to 89.4% (*Simulated result*). All simulated outputs are prominently labelled with `<TypeLabel type="simulated_result" />` in the UI to prevent operator overreach (R7).

---

### Decisions and trade-offs
1. **Deterministic Rules over End-to-End LLM Generation:** Rather than letting the LLM decide queues or priorities, the LLM only extracts semantic tags; deterministic Python functions calculate routing. This eliminated hallucinated priorities and ensured unit-testable consistency.
2. **Strict Grounding over Conversational Fluency:** Draft replies reject generative extrapolation. If an order number or customer name is not present in the ticket, Groundwork leaves an explicit bracket placeholder rather than inventing details.

[GAUTAM TO COMPLETE: Describe personal trade-offs encountered between development speed, model latency, and verification rigor.]

---

### What I would do next
1. **Active Learning Queue:** Implement an automated workflow for tickets rejected or edited by human reviewers to flag edge cases for queue configuration updates.
2. **Multilingual Expansion:** Expand signal detection calibration for non-English and multilingual Hinglish vernaculars beyond the current 14 evaluation tickets.
3. **Live Webhook Integration:** Connect the ingest engine to production CRM webhooks (e.g., Zendesk, Gorgias) with encrypted credential storage.

[GAUTAM TO COMPLETE: Add concluding thoughts on lessons learned and future technical roadmap for enterprise deployment.]
