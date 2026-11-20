# Stage 04: Outcomes (Measure)

## 1. Purpose

The Outcomes stage closes the loop on Groundwork engagements (Discover -> Diagnose -> Build -> Measure). It allows operators and clients to:
1. Define quantifiable operational targets grounded in empirical baselines.
2. Prioritise interventions using multi-criteria weighted scoring.
3. Simulate prospective pilot impacts deterministically under explicit assumptions.
4. Draft and confirm an evidence-based outcome review before any client-facing recommendations are presented.

In accordance with Groundwork non-negotiable rules (AGENTS.md R1-R12), no metrics are ever estimated or invented by language models; all numbers derive from deterministic, unit-tested Python functions in `backend/metrics/` and `backend/app/outcomes/simulation.py`.

---

## 2. KPI Catalogue & Target Rules

The KPI framework supports 6 standardized operational metrics defined in `config/outcomes.yaml`:

| Metric ID | Name | Direction | Unit | Baseline Source |
|---|---|---|---|---|
| `first_response_time` | Median First Response Time | `lower_is_better` | hours | `backend.metrics.response_time.first_response_time` |
| `resolution_time` | Median Resolution Time | `lower_is_better` | hours | `backend.metrics.response_time.resolution_time` |
| `customer_effort` | Customer Dissatisfaction / Effort Rate | `lower_is_better` | % | `backend.metrics.csat.csat_metrics` |
| `cost_per_contact` | Cost per Contact | `lower_is_better` | $ | `backend.metrics.cost.cost_per_ticket` |
| `reassignment_rate` | Reassignment Rate | `lower_is_better` | % | `backend.metrics.reassignment.reassignment_rate` |
| `sla_attainment` | SLA Attainment Rate | `higher_is_better` | % | `backend.metrics.sla.sla_attainment` |

### Baseline & Target Invariants
- **Active Dataset Requirement**: KPIs can only be created or recomputed when an active dataset is loaded (`422 Unprocessable Content` otherwise).
- **Target Improvement Rule**: Targets must lie strictly on the improvement side of the baseline (`target < baseline` for `lower_is_better`, `target > baseline` for `higher_is_better`). Targets on the worsening side are rejected with `422`.
- **Target Assumption**: Operators must supply a substantive rationale (`target_assumption`, at least 10 characters) explaining how the target will be achieved.
- **Planned Change**: The difference between target and baseline is computed as `target - baseline` (along with percentage change relative to baseline). To prevent misrepresentation, this figure is strictly labelled **"Planned change, not an outcome"** via `<TypeLabel>` and must never be cited as an achieved outcome before measurement.
- **Staleness Tracking**: If the engagement's active dataset changes, existing KPI baselines are flagged as stale (`is_stale: true`) until the operator explicitly triggers a recompute.
- **Primary KPI**: Exactly one KPI may be designated as primary per engagement.

---

## 3. Intervention Prioritisation

Interventions represent planned operational or tooling changes (e.g. automated triage routing, template assist).

### Multi-Criteria Scoring Formula
Each intervention is scored on a 1..5 scale across three dimensions:
- **Impact** ($I \in [1, 5]$): Expected magnitude of benefit (higher is better).
- **Effort** ($E \in [1, 5]$): Implementation complexity/workload (lower effort is better).
- **Risk** ($R \in [1, 5]$): Operational or customer risk (lower risk is better).

The composite prioritisation score is computed deterministically:
$$\text{Score} = 0.5 \times I + 0.3 \times (6 - E) + 0.2 \times (6 - R)$$

The score ranges from 1.0 (lowest priority: $I=1, E=5, R=5$) to 5.0 (highest priority: $I=5, E=1, R=1$). Interventions are presented sorted descending by score.

### Seeded Interventions
When first accessing interventions, Groundwork seeds four catalogue items from `config/outcomes.yaml`:
1. *Automated category & priority routing* (Impact 4, Effort 2, Risk 2 -> Score 3.8)
2. *Macro & canned response overhaul* (Impact 3, Effort 2, Risk 1 -> Score 3.7)
3. *Tier-1 self-service knowledge base* (Impact 4, Effort 4, Risk 3 -> Score 3.2)
4. *Queue re-balancing & staffing schedule* (Impact 3, Effort 3, Risk 2 -> Score 3.2)

---

## 4. Deterministic Pilot Simulation

To model potential outcomes before operational deployment, Groundwork provides a deterministic pilot simulation.

### Important Interpretation Limits
> [!WARNING]
> **Simulation is an assumption exploration tool, not a forecast.**
> The pilot simulation applies assumed effects to historical data; it demonstrates what the mathematical assumptions imply, but provides **zero empirical evidence** that the intervention will work in production. All simulation figures are visibly labelled with the **"Simulated result"** `<TypeLabel>`.

### Algorithm Specification
1. **Population**: historical tickets satisfying response and triage criteria ($created\_at$, $assigned\_at$, and $first\_response\_at$ present), ordered by row ID ascending.
2. **Partitioning**: Tickets are partitioned into a pilot group ($N_{pilot} = \lfloor N \times \text{pilot\_share} \rfloor$) and comparison group ($N_{comp} = N - N_{pilot}$) using the deterministic NumPy Mersenne Twister / PCG64 generator seeded by `seed`.
3. **Treatment Allocation**: In the pilot group, tickets receive treatment with probability:
   $$p_{treat} = \text{adoption\_pct} \times (1 - \text{rework\_share})$$
   where `rework_share` defaults to the latest completed evaluation run's `reviewer_change_proxy` figure (capturing human corrections needed).
4. **Effect Application**: Treated tickets experience reduced triage time:
   $$FRT_{treated} = FRT_{before} - (\text{reduction\_pct} \times TriageTime)$$
5. **Statistics & Confidence Interval**:
   - Compares median FRT between pilot-after and comparison groups.
   - Computes a 95% bootstrap confidence interval (2,000 resamples, seeded by `seed + 1`) for difference of medians.
   - Computes SLA attainment percentage for both groups against configured thresholds.
6. **Sensitivity Grid**: Evaluates a $3 \times 3$ grid across reduction percentages (25%, 50%, 75%) and adoption percentages (50%, 80%, 100%) to demonstrate parameter sensitivity.

---

## 5. Outcome Review & Human Approval

The Outcome Review synthesizes engagement objectives, KPI baselines and targets, evaluation results, and simulation outcomes into an executive summary.

### Snapshot Isolation & Untrusted Data
The review generation pipeline constructs an aggregate-only data snapshot containing NO individual ticket IDs, customer text, or PII. In the LLM prompt, the snapshot is serialized inside `<snapshot>...</snapshot>` tags and explicitly declared as untrusted data that must not dictate system instructions.

### Post-Processing Validation Flags
Every draft generated by the LLM is deterministically scanned by `postprocess_outcome_review`:
- `missing_evidence_key`: Cites a metric or parameter path that does not exist in the snapshot.
- `ungrounded_number`: Mentions numerical quantities not present in the aggregate snapshot.
- `simulated_claim_without_simulated_wording`: Discusses simulated outcomes without explicit "simulated" or "modelled" qualifiers.
- `basis_mismatch`: Mentions unachieved future targets as measured outcomes.
- `causal_wording`: Uses unsupported causal claims (e.g. "caused", "proves").

### Human Confirmation Lifecycle
- **Draft Status**: AI drafts and operator manual edits remain in `draft` status until explicitly confirmed.
- **Confirmation Flow**: The operator must explicitly acknowledge simulated data limits and select a final recommendation (`continue`, `iterate`, `pivot`, or `stop`).
- **Edit Revocation**: Any subsequent edit to a confirmed review automatically revokes confirmation (`status` reverts to `draft` and `confirmed_at` is cleared), ensuring unreviewed changes cannot be presented.
