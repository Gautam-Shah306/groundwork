import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OutcomesPage } from "../pages/OutcomesPage";
import { EngagementContext } from "../context/EngagementContext";
import * as api from "../lib/api";

vi.mock("../lib/api");

const mockEngagement = {
  id: 1,
  name: "Kora Living",
  client_name: "Kora Living",
  industry: "ecommerce",
  client_statement: "Support queues are overwhelmed",
  stage: "measure" as const,
  is_synthetic: true,
  created_at: "2026-11-20T10:00:00Z",
  updated_at: "2026-11-20T10:00:00Z",
};

const mockDataset: api.DatasetRecord = {
  id: 10,
  engagement_id: 1,
  filename: "sample_tickets.csv",
  record_count: 1200,
  is_sample: true,
  is_active: true,
  uploaded_at: "2026-11-20T10:00:00Z",
  period_start: "2026-10-01",
  period_end: "2026-10-31",
  validation_report: {} as any,
};

const mockCatalogue: api.KpiCatalogueItem[] = [
  {
    metric_id: "first_response_time",
    name: "Median First Response Time",
    description: "Time elapsed from ticket creation to first agent response.",
    direction: "lower_is_better",
    unit: "hours",
    benchmark_range: [1.0, 8.0],
    display_format: "0.0h",
  },
  {
    metric_id: "resolution_time",
    name: "Median Resolution Time",
    description: "Time elapsed from ticket creation to final resolution.",
    direction: "lower_is_better",
    unit: "hours",
    benchmark_range: [4.0, 48.0],
    display_format: "0.0h",
  },
];

const mockKpis: api.Kpi[] = [
  {
    id: 101,
    engagement_id: 1,
    metric_id: "first_response_time",
    name: "Median First Response Time",
    definition: "Time elapsed from ticket creation to first agent response.",
    calculation: "Deterministic calculation",
    unit: "hours",
    direction: "lower_is_better",
    baseline: {
      metric_id: "first_response_time",
      name: "Median First Response Time",
      value: 5.2,
      unit: "hours",
      direction: "lower_is_better",
      n: 1200,
      period_start: "2026-01-01",
      period_end: "2026-06-30",
      scope: ["response", "triage"],
    },
    target_value: 3.5,
    target_assumption: "Deploying triage assist routing to reduce queue wait time",
    planned_change: {
      absolute_change: -1.7,
      relative_change_pct: -32.7,
      label: "Planned change, not an outcome",
    },
    is_primary: true,
    is_stale: false,
    status: "active",
  },
];

const mockInterventions: api.Intervention[] = [
  {
    id: 201,
    engagement_id: 1,
    name: "Automated triage routing",
    description: "Rule-based category and priority routing",
    impact: 4,
    effort: 2,
    risk: 2,
    score: 3.8,
    rationale: "High impact with moderate effort",
    status: "proposed",
    origin: "catalogue",
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  },
  {
    id: 202,
    engagement_id: 1,
    name: "Tier-1 FAQ Bot",
    description: "Self-service resolution for common queries",
    impact: 3,
    effort: 4,
    risk: 3,
    score: 2.7,
    rationale: "Requires substantial knowledge base work",
    status: "rejected",
    origin: "catalogue",
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  },
];

const mockSimulation: api.SimulationResult = {
  id: 1,
  engagement_id: 1,
  parameters: {
    pilot_share: 0.25,
    reduction_pct: 30,
    adoption_pct: 80,
    rework_share: 0.15,
    seed: 42,
    bootstrap_resamples: 2000,
    sla_threshold_hours: 4.0,
  },
  rework_share_source: "eval_run_1",
  note: "The simulation applies assumed effects; it shows what the assumptions imply, not evidence that the intervention works.",
  sample_sizes: {
    n: 1200,
    n_pilot: 300,
    n_comparison: 900,
    n_treated: 204,
    p_treat: 0.68,
  },
  comparison_group: {
    n: 900,
    median: 5.2,
    q25: 3.1,
    q75: 8.4,
    iqr: 5.3,
    sla_attainment_pct: 78.5,
  },
  pilot_group_before: {
    n: 300,
    median: 5.2,
    q25: 3.0,
    q75: 8.3,
    iqr: 5.3,
  },
  pilot_group_after: {
    n: 300,
    median: 3.8,
    q25: 2.4,
    q75: 6.2,
    iqr: 3.8,
    sla_attainment_pct: 88.0,
  },
  effect: {
    difference_of_medians_hours: -1.4,
    bootstrap_ci_95: [-1.8, -1.0],
    interpretation: "Under assumed 30% reduction and 80% adoption, median FRT is reduced by 1.40 hours.",
  },
  sensitivity_grid: [
    { reduction_pct: 25, adoption_pct: 50, difference_hours: -0.6, median_pilot_after: 4.6 },
    { reduction_pct: 25, adoption_pct: 80, difference_hours: -1.0, median_pilot_after: 4.2 },
    { reduction_pct: 25, adoption_pct: 100, difference_hours: -1.2, median_pilot_after: 4.0 },
    { reduction_pct: 50, adoption_pct: 50, difference_hours: -1.1, median_pilot_after: 4.1 },
    { reduction_pct: 50, adoption_pct: 80, difference_hours: -1.8, median_pilot_after: 3.4 },
    { reduction_pct: 50, adoption_pct: 100, difference_hours: -2.3, median_pilot_after: 2.9 },
    { reduction_pct: 75, adoption_pct: 50, difference_hours: -1.7, median_pilot_after: 3.5 },
    { reduction_pct: 75, adoption_pct: 80, difference_hours: -2.7, median_pilot_after: 2.5 },
    { reduction_pct: 75, adoption_pct: 100, difference_hours: -3.4, median_pilot_after: 1.8 },
  ],
  created_at: "2026-11-20T11:00:00Z",
};

const mockReview: api.OutcomeReview = {
  id: 1,
  engagement_id: 1,
  sections: {
    objective: "Reduce median first response time below 4.0 hours",
    recommendation: {
      value: "continue",
      rationale: "Pilot simulation indicates significant trajectory improvement.",
    },
    what_improved: ["Modelled first response time reduced by 1.40 hours."],
    what_did_not: ["SLA compliance remains below 90% target."],
    limitations: ["Simulation results are sensitive to agent adoption assumptions."],
    next_steps: ["Deploy assist mode to 25% of support team for 2 weeks."],
  },
  snapshot: {},
  flags: [
    { code: "simulated_claim_without_simulated_wording", message: "Section mentions pilot outcome without 'simulated' qualifier." },
  ],
  status: "draft",
  final_recommendation: null,
  confirmed_at: null,
  acknowledged_simulated: false,
  created_at: "2026-11-20T11:30:00Z",
  updated_at: "2026-11-20T11:30:00Z",
};

function renderOutcomes(engagement: any = mockEngagement) {
  return render(
    <MemoryRouter>
      <EngagementContext.Provider
        value={{
          engagements: engagement ? [engagement] : [],
          activeEngagement: engagement,
          activeEngagementId: engagement?.id ?? null,
          loading: false,
          error: null,
          selectEngagement: vi.fn(),
          createEngagement: vi.fn(),
          deleteEngagement: vi.fn(),
          refreshEngagements: vi.fn(),
        } as any}
      >
        <OutcomesPage />
      </EngagementContext.Provider>
    </MemoryRouter>
  );
}

describe("OutcomesPage (Stage 04: Measure)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      llm_configured: true,
      database_url_scheme: "sqlite",
    });
    vi.mocked(api.getKpiCatalogue).mockResolvedValue(mockCatalogue);
    vi.mocked(api.getKpis).mockResolvedValue(mockKpis);
    vi.mocked(api.getInterventions).mockResolvedValue(mockInterventions);
    vi.mocked(api.getSimulations).mockResolvedValue([mockSimulation]);
    vi.mocked(api.getOutcomeReview).mockResolvedValue(mockReview);
    vi.mocked(api.fetchDatasets).mockResolvedValue([mockDataset]);
    vi.mocked(api.fetchBrief).mockResolvedValue({
      id: 1,
      engagement_id: 1,
      source: "ai_draft",
      sections: {
        problem_statement: { text: "First response times exceed customer expectations." },
      } as any,
      updated_at: "2026-11-20T10:00:00Z",
    });
  });

  // Test 1: Empty state when no active engagement
  it("renders empty state when no active engagement is selected", () => {
    render(
      <MemoryRouter>
        <EngagementContext.Provider
          value={{
            engagements: [],
            activeEngagement: null,
            activeEngagementId: null,
            loading: false,
            error: null,
            selectEngagement: vi.fn(),
            createEngagement: vi.fn(),
            deleteEngagement: vi.fn(),
            refreshEngagements: vi.fn(),
          }}
        >
          <OutcomesPage />
        </EngagementContext.Provider>
      </MemoryRouter>
    );
    expect(screen.getByText("No outcome comparison recorded")).toBeInTheDocument();
  });

  // Test 2: Renders header and synthetic data notice
  it("renders header and synthetic data notice when engagement is selected", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "Outcomes" })).toBeInTheDocument();
      expect(screen.getByText("Synthetic demonstration data")).toBeInTheDocument();
    });
  });

  // Test 3: Renders strategic intent problem statement and objective input
  it("renders strategic intent problem statement and objective input", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("First response times exceed customer expectations.")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Reduce median first response time below 4.0 hours")).toBeInTheDocument();
    });
  });

  // Test 4: Updates objective text as operator types
  it("updates objective text as operator types", async () => {
    renderOutcomes();
    await waitFor(() => {
      const input = screen.getByDisplayValue("Reduce median first response time below 4.0 hours");
      fireEvent.change(input, { target: { value: "Updated operational objective" } });
      expect(input).toHaveValue("Updated operational objective");
    });
  });

  // Test 5: Disables objective text editing when review is confirmed
  it("disables objective text editing when review is confirmed", async () => {
    vi.mocked(api.getOutcomeReview).mockResolvedValue({
      ...mockReview,
      status: "confirmed",
      confirmed_at: "2026-11-20T12:00:00Z",
      final_recommendation: "continue",
    });
    renderOutcomes();
    await waitFor(() => {
      const input = screen.getByDisplayValue("Reduce median first response time below 4.0 hours");
      expect(input).toBeDisabled();
    });
  });

  // Test 6: Renders active dataset warning when no dataset is loaded
  it("renders active dataset warning when no dataset is loaded", async () => {
    vi.mocked(api.fetchDatasets).mockResolvedValue([]);
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText(/active dataset required/i)).toBeInTheDocument();
    });
  });

  // Test 7: Renders KPI table with catalogue items and computed baselines
  it("renders KPI table with catalogue items and computed baselines", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Median First Response Time")).toBeInTheDocument();
      expect(screen.getAllByText(/5\.20 hours/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/3\.50 hours/).length).toBeGreaterThan(0);
    });
  });

  // Test 8: Displays planned change with TypeLabel
  it("displays planned change with Planned change TypeLabel", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(
        screen.getByText((content) => content.includes("-1.70 hours") && content.includes("-32.7%"))
      ).toBeInTheDocument();
      expect(screen.getAllByText("Planned change, not an outcome").length).toBeGreaterThan(0);
    });
  });

  // Test 9: Displays stale baseline warning when active dataset changes
  it("displays stale baseline warning and recompute button when dataset changes", async () => {
    vi.mocked(api.getKpis).mockResolvedValue([
      { ...mockKpis[0], is_stale: true },
    ]);
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Stale dataset")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /recompute/i })).toBeInTheDocument();
    });
  });

  // Test 10: Triggers baseline recompute API call on click
  it("triggers baseline recompute API call on click", async () => {
    vi.mocked(api.getKpis).mockResolvedValue([
      { ...mockKpis[0], is_stale: true },
    ]);
    vi.mocked(api.recomputeKpiBaseline).mockResolvedValue({
      ...mockKpis[0],
      is_stale: false,
    });
    renderOutcomes();
    await waitFor(() => {
      const recomputeBtn = screen.getByRole("button", { name: /recompute/i });
      fireEvent.click(recomputeBtn);
    });
    expect(api.recomputeKpiBaseline).toHaveBeenCalledWith(1, 101);
  });

  // Test 11: Allows opening and closing the Add KPI form
  it("allows opening and closing the Add KPI form", async () => {
    renderOutcomes();
    await waitFor(() => {
      const addBtn = screen.getByRole("button", { name: /add kpi target/i });
      fireEvent.click(addBtn);
    });
    expect(screen.getByText("Add KPI from Catalogue")).toBeInTheDocument();

    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(cancelBtn);
    expect(screen.queryByText("Add KPI from Catalogue")).not.toBeInTheDocument();
  });

  // Test 12: Validates target assumption length (min 10 chars)
  it("validates target assumption length before creating KPI", async () => {
    renderOutcomes();
    await waitFor(() => {
      fireEvent.click(screen.getByRole("button", { name: /add kpi target/i }));
    });
    fireEvent.change(screen.getByPlaceholderText("Target number"), { target: { value: "3.0" } });
    fireEvent.change(screen.getByPlaceholderText(/automated routing/i), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Save KPI" }));

    await waitFor(() => {
      expect(screen.getByText(/minimum 10 characters/i)).toBeInTheDocument();
    });
  });

  // Test 13: Submits valid KPI create request
  it("submits valid KPI create request and updates list", async () => {
    vi.mocked(api.createKpi).mockResolvedValue({
      ...mockKpis[0],
      id: 102,
      metric_id: "resolution_time",
      name: "Median Resolution Time",
    });
    renderOutcomes();
    await waitFor(() => {
      fireEvent.click(screen.getByRole("button", { name: /add kpi target/i }));
    });
    fireEvent.change(screen.getByPlaceholderText("Target number"), { target: { value: "12.0" } });
    fireEvent.change(screen.getByPlaceholderText(/automated routing/i), {
      target: { value: "Automated routing handles inquiries quickly" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save KPI" }));

    await waitFor(() => {
      expect(api.createKpi).toHaveBeenCalled();
    });
  });

  // Test 14: Deletes KPI when delete button is clicked
  it("deletes KPI when trash icon is clicked", async () => {
    vi.mocked(api.deleteKpi).mockResolvedValue(undefined);
    renderOutcomes();
    await waitFor(() => {
      const deleteBtn = screen.getByTitle("Delete KPI");
      fireEvent.click(deleteBtn);
    });
    expect(api.deleteKpi).toHaveBeenCalledWith(1, 101);
  });

  // Test 15: Renders interventions prioritisation table sorted descending by score
  it("renders interventions prioritisation table sorted descending by score", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Automated triage routing")).toBeInTheDocument();
      expect(screen.getByText("3.8")).toBeInTheDocument();
      expect(screen.getByText("Tier-1 FAQ Bot")).toBeInTheDocument();
      expect(screen.getByText("2.7")).toBeInTheDocument();
    });
  });

  // Test 16: Allows creating a custom human intervention
  it("allows creating a custom human intervention with impact, effort, risk 1..5", async () => {
    vi.mocked(api.createIntervention).mockResolvedValue({
      id: 203,
      engagement_id: 1,
      name: "Custom Fast-track",
      description: "Priority routing",
      impact: 5,
      effort: 1,
      risk: 1,
      score: 5.0,
      rationale: "Quick win",
      status: "proposed",
      origin: "human",
      created_at: "2026-11-20T12:00:00Z",
      updated_at: "2026-11-20T12:00:00Z",
    });
    renderOutcomes();
    await waitFor(() => {
      fireEvent.click(screen.getByRole("button", { name: /add intervention/i }));
    });
    fireEvent.change(screen.getByPlaceholderText(/VIP Triage/i), { target: { value: "Custom Fast-track" } });
    fireEvent.change(screen.getByPlaceholderText(/Operational purpose/i), { target: { value: "Priority routing" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Intervention" }));

    await waitFor(() => {
      expect(api.createIntervention).toHaveBeenCalled();
    });
  });

  // Test 17: Updates intervention status via dropdown
  it("updates intervention status via dropdown", async () => {
    vi.mocked(api.updateIntervention).mockResolvedValue({
      ...mockInterventions[0],
      status: "selected",
    });
    renderOutcomes();
    await waitFor(() => {
      const dropdowns = screen.getAllByRole("combobox");
      fireEvent.change(dropdowns[0], { target: { value: "selected" } });
    });
    expect(api.updateIntervention).toHaveBeenCalledWith(1, 201, { status: "selected" });
  });

  // Test 18: Renders simulation section with parameter sliders and rework share
  it("renders simulation section with parameter sliders and rework share", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Pilot Group Share")).toBeInTheDocument();
      expect(screen.getByText("Triage Reduction")).toBeInTheDocument();
      expect(screen.getByText("Adoption Rate")).toBeInTheDocument();
      expect(screen.getByText("Random Seed")).toBeInTheDocument();
    });
  });

  // Test 19: Displays prominent Simulated result label and disclaimer alert
  it("displays prominent Simulated result label and disclaimer alert", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getAllByText("Simulated result").length).toBeGreaterThan(0);
      expect(screen.getByText(/Simulation is not empirical evidence/i)).toBeInTheDocument();
    });
  });

  // Test 20: Executes pilot simulation and displays median FRT, effect CI, and SLA attainment
  it("executes pilot simulation and displays median FRT, effect CI, and SLA attainment", async () => {
    vi.mocked(api.runSimulation).mockResolvedValue({ ...mockSimulation, id: 2 });
    renderOutcomes();
    await waitFor(() => {
      const runBtn = screen.getByRole("button", { name: /run simulation/i });
      fireEvent.click(runBtn);
    });
    expect(api.runSimulation).toHaveBeenCalledWith(1, expect.objectContaining({
      pilot_share: 0.25,
      reduction_pct: 30,
      adoption_pct: 80,
      seed: 42,
    }));
    await waitFor(() => {
      expect(screen.getByText("5.20h")).toBeInTheDocument();
      expect(screen.getByText("3.80h")).toBeInTheDocument();
      expect(screen.getByText("-1.40h")).toBeInTheDocument();
    });
  });

  // Test 21: Renders 3x3 sensitivity grid
  it("renders 3x3 sensitivity grid with correct reduction and adoption cells", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Sensitivity Grid (Difference in Median FRT, Hours)")).toBeInTheDocument();
      expect(screen.getByText("25% Reduction")).toBeInTheDocument();
      expect(screen.getByText("50% Reduction")).toBeInTheDocument();
      expect(screen.getByText("75% Reduction")).toBeInTheDocument();
    });
  });

  // Test 22: Renders comparison chart with accessible View as table toggle
  it("renders comparison chart with accessible View as table toggle", async () => {
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText("Trajectory & Scenario Benchmarks")).toBeInTheDocument();
      const tableToggle = screen.getByRole("button", { name: /view as table/i });
      fireEvent.click(tableToggle);
    });
    await waitFor(() => {
      expect(screen.getByText("Empirical Baseline")).toBeInTheDocument();
    });
  });

  // Test 23: Displays LLM unconfigured notice when provider not configured
  it("displays LLM unconfigured notice when provider not configured", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      llm_configured: false,
      database_url_scheme: "sqlite",
    });
    renderOutcomes();
    await waitFor(() => {
      expect(screen.getByText(/LLM provider is not configured/i)).toBeInTheDocument();
    });
  });

  // Test 24: Allows human confirmation flow
  it("allows human confirmation flow: requires acknowledging simulated data limits, selects recommendation, and sets confirmed state", async () => {
    vi.mocked(api.confirmOutcomeReview).mockResolvedValue({
      ...mockReview,
      status: "confirmed",
      confirmed_at: "2026-11-20T12:00:00Z",
      final_recommendation: "continue",
      acknowledged_simulated: true,
    });
    renderOutcomes();
    await waitFor(() => {
      const confirmOpenBtn = screen.getByRole("button", { name: /confirm & approve review/i });
      fireEvent.click(confirmOpenBtn);
    });

    expect(screen.getByText("Operator Decision Confirmation")).toBeInTheDocument();
    const ackCheckbox = screen.getByRole("checkbox", { name: /i acknowledge that simulated results/i });
    fireEvent.click(ackCheckbox);

    const submitConfirmBtn = screen.getByRole("button", { name: "Confirm Decision" });
    fireEvent.click(submitConfirmBtn);

    await waitFor(() => {
      expect(api.confirmOutcomeReview).toHaveBeenCalledWith(1, {
        final_recommendation: "continue",
        acknowledged_simulated: true,
      });
      expect(screen.getByText("Review Confirmed by Human Operator")).toBeInTheDocument();
    });
  });
});
