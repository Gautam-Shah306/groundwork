import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { DiagnosticsAnalysis } from "../components/diagnostics/DiagnosticsAnalysis";
import type {
  DatasetRecord,
  DiagnosticsResponse,
  Engagement,
} from "../lib/api";
import { CHART_COLORS } from "../lib/chartColors";

const ENGAGEMENT: Engagement = {
  id: 1,
  name: "Kora Living: Customer support turnaround",
  client_name: "Kora Living",
  industry: "D2C home-goods retail",
  client_statement: "Customers are waiting too long for responses.",
  stage: "diagnose",
  is_synthetic: true,
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-18T08:00:00Z",
};

const SAMPLE_DATASET: DatasetRecord = {
  id: 10,
  engagement_id: 1,
  filename: "sample_tickets.csv",
  is_sample: true,
  is_active: true,
  uploaded_at: "2026-11-18T10:00:00Z",
  record_count: 2000,
  period_start: "2026-09-07T00:00:00Z",
  period_end: "2026-11-01T18:29:59Z",
  validation_report: {
    record_count: 2000,
    period_start: "2026-09-07T00:00:00Z",
    period_end: "2026-11-01T18:29:59Z",
    distinct_ticket_ids: 1997,
    distinct_customers: 1269,
    dataset_warnings: [],
    rows_valid_for_all_metrics: 1991,
    excluded_by_scope: {
      all_metrics: 9,
      response_metrics: 29,
      resolution_metrics: 22,
      triage_metrics: 9,
    },
    checks: [],
  },
};

function makeDiagnosticsResponse(
  overrides: Partial<DiagnosticsResponse> = {}
): DiagnosticsResponse {
  return {
    dataset: {
      id: 10,
      engagement_id: 1,
      filename: "sample_tickets.csv",
      is_sample: true,
      is_active: true,
      uploaded_at: "2026-11-18T10:00:00Z",
      record_count: 2000,
      period_start: "2026-09-07T00:00:00Z",
      period_end: "2026-11-01T18:29:59Z",
    },
    as_of: "2026-11-01T18:29:59Z",
    timezone: "Asia/Kolkata",
    scope_summary: {
      total_rows: 2000,
      rows_valid_for_all_metrics: 1991,
      excluded_by_scope: {
        all_metrics: 9,
        response_metrics: 29,
        resolution_metrics: 22,
        triage_metrics: 9,
      },
    },
    kpis: [
      {
        metric_id: "first_response_time",
        name: "Median first response",
        value: 6.07,
        unit: "hours",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1971,
        n_excluded: 29,
        exclusions: { first_response_before_created: 8, duplicate_ticket_id: 3 },
        definition: "Median elapsed hours from created_at to first_response_at.",
        scope: "response_metrics",
        note: null,
      },
      {
        metric_id: "triage_time",
        name: "Median triage time",
        value: 3.7,
        unit: "hours",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1991,
        n_excluded: 9,
        exclusions: { duplicate_ticket_id: 3, unknown_category: 6 },
        definition: "Median elapsed hours from created_at to assigned_at.",
        scope: "triage_metrics",
        note: null,
      },
      {
        metric_id: "resolution_time",
        name: "Median resolution time",
        value: 22.22,
        unit: "hours",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1706,
        n_excluded: 22,
        exclusions: { implausible_duration: 4 },
        definition: "Median elapsed hours from created_at to resolved_at.",
        scope: "resolution_metrics",
        note: null,
      },
      {
        metric_id: "sla_attainment",
        name: "First-response SLA attainment",
        value: 14.61,
        unit: "%",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1971,
        n_excluded: 29,
        exclusions: { first_response_before_created: 8 },
        definition:
          "Percentage of responded tickets meeting the 4.0 h first-response threshold.",
        scope: "response_metrics",
        note: "Illustrative threshold from configuration, not agreed with the client",
      },
      {
        metric_id: "backlog_ageing",
        name: "Open backlog",
        value: 272,
        unit: "tickets",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1991,
        n_excluded: 9,
        exclusions: { duplicate_ticket_id: 3 },
        definition: "Count of open/pending tickets at dataset period end.",
        scope: "all_metrics",
        note: null,
      },
      {
        metric_id: "reassignment_rate",
        name: "Reassignment rate",
        value: 21.2,
        unit: "%",
        period_start: "2026-09-07T00:00:00Z",
        period_end: "2026-11-01T18:29:59Z",
        n: 1991,
        n_excluded: 9,
        exclusions: { duplicate_ticket_id: 3, unknown_category: 6 },
        definition: "Percentage of valid tickets reassigned at least once.",
        scope: "all_metrics",
        note: null,
      },
    ],
    metrics: {
      volume_by_hour: {
        metric_id: "volume_by_hour",
        title: "Ticket volume by hour of day (IST)",
        unit: "tickets",
        n_included: 1991,
        n_excluded: 9,
        exclusions: { duplicate_ticket_id: 3, unknown_category: 6 },
        definition: "Ticket counts per IST hour.",
        scope: "all_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: [
          { hour: 9, count: 142, share: 0.07 },
          { hour: 19, count: 215, share: 0.11 },
        ],
      },
      volume_by_day: {
        metric_id: "volume_by_day",
        title: "Daily ticket volume (IST)",
        unit: "tickets",
        n_included: 1991,
        n_excluded: 9,
        exclusions: { duplicate_ticket_id: 3 },
        definition: "Daily ticket counts in IST.",
        scope: "all_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: [
          { date: "2026-09-07", count: 38, share: 0.02 },
          { date: "2026-09-08", count: 41, share: 0.02 },
        ],
      },
      first_response_by_band: {
        metric_id: "first_response_by_band",
        title: "First-response time by creation band",
        unit: "hours",
        n_included: 1971,
        n_excluded: 29,
        exclusions: {},
        definition: "Median and p90 first-response hours per creation band.",
        scope: "response_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: [
          { band: "afternoon", hours: "14:00-18:00", n: 452, median: 4.79, p90: 7.55, mean: 5.13 },
          { band: "evening", hours: "18:00-22:00", n: 432, median: 7.45, p90: 11.63, mean: 8.01 },
        ],
      },
      backlog_ageing: {
        metric_id: "backlog_ageing",
        title: "Backlog ageing",
        unit: "tickets",
        n_included: 1991,
        n_excluded: 9,
        exclusions: {},
        definition: "Age buckets of open/pending tickets.",
        scope: "all_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: {
          total_open_backlog: 272,
          oldest_age_days: 12.4,
          buckets: [
            { bucket: "<1d", min_days: 0, max_days: 1, count: 40, share: 0.15 },
            { bucket: "7d+", min_days: 7, max_days: null, count: 95, share: 0.35 },
          ],
        },
      },
      agent_workload: {
        metric_id: "agent_workload",
        title: "Agent workload distribution",
        unit: "tickets",
        n_included: 1991,
        n_excluded: 9,
        exclusions: {},
        definition: "Tickets per agent, top-3 share and Gini.",
        scope: "all_metrics",
        params: { top_n: 3 },
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: {
          assigned_total: 1991,
          unassigned_count: 0,
          top_n: 3,
          top_n_agents: ["Agent 01", "Agent 02", "Agent 03"],
          top_n_share: 0.4,
          gini: 0.21,
          agents: [
            { agent: "Agent 01", count: 270, share: 0.14 },
            { agent: "Agent 02", count: 260, share: 0.13 },
          ],
        },
      },
      reassignment_rate: {
        metric_id: "reassignment_rate",
        title: "Reassignment rate",
        unit: "proportion",
        n_included: 1991,
        n_excluded: 9,
        exclusions: {},
        definition: "Share of tickets reassigned at least once.",
        scope: "all_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: {
          overall: { n: 1991, rate: 0.21 },
          by_category: [
            {
              category: "order_tracking",
              n: 583,
              reassigned_count: 195,
              rate: 0.33,
              mean_reassignments: 0.42,
            },
            {
              category: "payment_issues",
              n: 256,
              reassigned_count: 22,
              rate: 0.09,
              mean_reassignments: 0.1,
            },
          ],
        },
      },
      category_delay_table: {
        metric_id: "category_delay_table",
        title: "Category delay table",
        unit: "mixed",
        n_included: 1991,
        n_excluded: 9,
        exclusions: {},
        definition: "Per-category medians and reassignment rates.",
        scope: "all_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: [
          {
            category: "order_tracking",
            n: 583,
            median_triage_hours: 3.7,
            median_first_response_hours: 6.1,
            median_resolution_hours: 22.2,
            reassignment_rate: 0.33,
          },
        ],
      },
      factor_comparison: {
        metric_id: "factor_comparison",
        title: "Factor comparison",
        unit: "hours",
        n_included: 1971,
        n_excluded: 29,
        exclusions: {},
        definition: "Side-by-side median first-response comparison.",
        scope: "response_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: [
          {
            factor_id: "evening_vs_afternoon",
            factor: "Evening (18-22) vs afternoon (14-18) creation",
            group_a_label: "Evening (18:00-22:00 IST)",
            group_a_median_hours: 7.45,
            group_a_n: 432,
            group_b_label: "Afternoon (14:00-18:00 IST)",
            group_b_median_hours: 4.79,
            group_b_n: 452,
            difference_hours: 2.66,
            note: "Observed association only; groups overlap across other factors.",
          },
        ],
      },
      triage_share_of_first_response: {
        metric_id: "triage_share_of_first_response",
        title: "Triage share of first response",
        unit: "proportion",
        n_included: 1971,
        n_excluded: 29,
        exclusions: {},
        definition: "Sum of triage hours divided by sum of first-response hours.",
        scope: "response_metrics+triage_metrics",
        params: {},
        notes: [],
        as_of: "2026-11-01T18:29:59Z",
        data: { share: 0.65 },
      },
    },
    findings: [
      // Deliberately out of order to verify client-side sorting by strength
      {
        id: "F-INSUFF",
        title: "Limited evening sample check",
        status: "insufficient_data",
        strength: null,
        observation: {
          type: "observed_fact",
          text: "Only 12 rows were available for this comparison.",
        },
        hypothesis: {
          type: "hypothesis",
          text: "Sample size is below the minimum threshold of 30 rows.",
        },
        evidence: [
          {
            metric_id: "first_response_by_band",
            label: "Evening sample",
            value: 12,
            unit: "tickets",
            n: 12,
            params: { band: "evening" },
          },
        ],
        limitations: ["Fewer than 30 rows available."],
        validation_questions: [
          {
            text: "Can an expanded date range be exported?",
            kind: "template_question",
            finding_id: "F-INSUFF",
          },
        ],
      },
      {
        id: "F-BACKLOG",
        title: "Unresolved tickets aged more than 7 days in backlog",
        status: "supported",
        strength: "moderate",
        observation: {
          type: "observed_fact",
          text: "95 open/pending tickets have been unresolved for over 7 days.",
        },
        hypothesis: {
          type: "hypothesis",
          text: "Aged tickets may be awaiting customer replies or external carrier confirmation.",
        },
        evidence: [
          {
            metric_id: "backlog_ageing",
            label: "Open > 7d",
            value: 95,
            unit: "tickets",
            n: 272,
            params: { bucket: "7d+" },
          },
        ],
        limitations: ["Status history transitions are not included in the CSV."],
        validation_questions: [
          {
            text: "Are aged open tickets waiting on customers or internal escalations?",
            kind: "template_question",
            finding_id: "F-BACKLOG",
          },
        ],
      },
      {
        id: "F-TRIAGE",
        title: "Time to assignment accounts for a large share of first-response time",
        status: "supported",
        strength: "strong",
        observation: {
          type: "observed_fact",
          text: "Median triage time (3.7 h) accounts for 65% of total first-response time.",
        },
        hypothesis: {
          type: "hypothesis",
          text: "Manual queue intake may be delaying initial assignment before an agent sees the ticket.",
        },
        evidence: [
          {
            metric_id: "triage_share_of_first_response",
            label: "Triage share",
            value: 65,
            unit: "%",
            n: 1971,
            params: {},
          },
        ],
        limitations: ["Does not separate automated rules from manual triage."],
        validation_questions: [
          {
            text: "How are new tickets currently assigned to agents?",
            kind: "template_question",
            finding_id: "F-TRIAGE",
          },
        ],
      },
    ],
    validation_questions: [
      {
        text: "How are new tickets currently assigned to agents?",
        kind: "template_question",
        finding_id: "F-TRIAGE",
      },
      {
        text: "What are the agreed first-response SLA targets?",
        kind: "template_question",
        finding_id: null,
      },
    ],
    ...overrides,
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DiagnosticsAnalysis & DiagnosticsPage integration", () => {
  it("1. analysis section is not rendered when there is no dataset", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/engagements")) {
        return jsonResponse([ENGAGEMENT]);
      }
      if (url.endsWith("/api/engagements/1/datasets")) {
        return jsonResponse([]);
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    await screen.findByText(/Upload operational ticket data/i);
    expect(screen.queryByTestId("diagnostics-analysis")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("diagnostics-analysis-skeleton")
    ).not.toBeInTheDocument();
  });

  it("2. shows a loading skeleton, then the KPI tiles", async () => {
    let resolveDiagnostics!: (res: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveDiagnostics = resolve;
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async () => pending);

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    expect(
      screen.getByTestId("diagnostics-analysis-skeleton")
    ).toBeInTheDocument();

    resolveDiagnostics(jsonResponse(makeDiagnosticsResponse()));

    await screen.findByTestId("diagnostics-analysis");
    expect(
      screen.queryByTestId("diagnostics-analysis-skeleton")
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("kpi-card-first_response_time")
    ).toBeInTheDocument();
    expect(screen.getByTestId("kpi-card-triage_time")).toBeInTheDocument();
  });

  it("3. KPI tile shows name, value, unit, period and n", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const card = await screen.findByTestId("kpi-card-first_response_time");
    expect(within(card).getByText("Median first response")).toBeInTheDocument();
    expect(within(card).getByText("6.07")).toBeInTheDocument();
    expect(within(card).getByText("hours")).toBeInTheDocument();
    expect(within(card).getByText(/Sep 7, 2026/)).toBeInTheDocument();
    expect(within(card).getByText("n = 1,971")).toBeInTheDocument();
  });

  it("4. KPI tiles show no target or improvement percentage", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const section = await screen.findByLabelText("Operational KPI summary");
    const cards = within(section).getAllByTestId(/^kpi-card-/);
    expect(cards).toHaveLength(6);

    for (const card of cards) {
      const text = card.textContent ?? "";
      expect(text).not.toMatch(/improvement/i);
      expect(text).not.toMatch(/saving/i);
      expect(text).not.toMatch(/\btarget:/i);
      expect(text).not.toMatch(/[+-]\d+(\.\d+)?%/);
    }
  });

  it("5. SLA tile shows the illustrative-threshold note", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const slaCard = await screen.findByTestId("kpi-card-sla_attainment");
    expect(
      within(slaCard).getByText(/Illustrative threshold/i)
    ).toBeInTheDocument();
  });

  it("6. how-this-is-calculated expander shows definition, scope and exclusions", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const card = await screen.findByTestId("kpi-card-first_response_time");
    const button = within(card).getByRole("button", {
      name: /How this is calculated/i,
    });
    expect(button).toHaveAttribute("aria-expanded", "false");

    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(
      within(card).getByText(
        /Median elapsed hours from created_at to first_response_at/i
      )
    ).toBeInTheDocument();
    expect(within(card).getByText(/response_metrics/i)).toBeInTheDocument();
    expect(
      within(card).getByText(/first_response_before_created: 8/i)
    ).toBeInTheDocument();
  });

  it("7. each chart has a title, an accessible name and a View as table toggle that reveals exact values", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);
    await screen.findByTestId("diagnostics-analysis");

    const chartChecks = [
      { title: "Ticket volume by hour of day (IST)", expectedCell: "215" },
      { title: "Daily ticket volume (IST)", expectedCell: "2026-09-07" },
      {
        title: "First-response time by creation band (hours)",
        expectedCell: "7.45",
      },
      { title: "Backlog ageing (open & pending tickets)", expectedCell: "7d+" },
      { title: "Agent workload distribution", expectedCell: "Agent 01" },
      { title: "Reassignment rate by category (%)", expectedCell: "33%" },
    ];

    for (const check of chartChecks) {
      const region = screen.getByRole("region", { name: check.title });
      expect(region).toBeInTheDocument();
      const card = region.closest("section");
      expect(card).not.toBeNull();
      expect(within(card!).getByText(check.title)).toBeInTheDocument();

      const toggleBtn = within(card!).getByRole("button", {
        name: "View as table",
      });
      await user.click(toggleBtn);

      const table = within(region).getByRole("table");
      expect(within(table).getByText(check.expectedCell)).toBeInTheDocument();
    }
  });

  it("8. chart colours come from the shared module and the same metric maps to the same colour in two charts", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);
    await screen.findByTestId("diagnostics-analysis");

    const hourRegion = screen.getByRole("region", {
      name: "Ticket volume by hour of day (IST)",
    });
    const dayRegion = screen.getByRole("region", {
      name: "Daily ticket volume (IST)",
    });

    expect(hourRegion).toHaveAttribute("data-metric-color", CHART_COLORS.volume);
    expect(dayRegion).toHaveAttribute("data-metric-color", CHART_COLORS.volume);
    expect(hourRegion.getAttribute("data-metric-color")).toBe(
      dayRegion.getAttribute("data-metric-color")
    );
  });

  it("9. factor comparison shows the 'Observed association, not a cause' caption", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);
    await screen.findByTestId("diagnostics-analysis");

    const matches = screen.getAllByText(/Observed association, not a cause/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/7\.45 h/)).toBeInTheDocument();
    expect(screen.getByText(/2\.66 h/)).toBeInTheDocument();
  });

  it("10. findings show Observed fact and Hypothesis labels separately, with Needs validation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const finding = await screen.findByTestId("finding-F-TRIAGE");
    expect(within(finding).getByText("Observed fact")).toBeInTheDocument();
    expect(within(finding).getByText("Hypothesis")).toBeInTheDocument();
    expect(within(finding).getByText("Needs validation")).toBeInTheDocument();
    expect(
      within(finding).getByText(/Median triage time \(3\.7 h\)/i)
    ).toBeInTheDocument();
    expect(
      within(finding).getByText(/Manual queue intake may be delaying/i)
    ).toBeInTheDocument();
  });

  it("11. expanding a finding shows evidence rows with metric id and value", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const finding = await screen.findByTestId("finding-F-TRIAGE");
    const evidenceBtn = within(finding).getByRole("button", {
      name: /Evidence \(1\)/i,
    });
    await user.click(evidenceBtn);

    expect(
      within(finding).getByText("triage_share_of_first_response")
    ).toBeInTheDocument();
    expect(within(finding).getByText("65 %")).toBeInTheDocument();
  });

  it("12. an insufficient-data finding is shown without a strength", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const finding = await screen.findByTestId("finding-F-INSUFF");
    expect(within(finding).getByText("Insufficient data")).toBeInTheDocument();
    expect(within(finding).queryByText("Strong")).not.toBeInTheDocument();
    expect(within(finding).queryByText("Moderate")).not.toBeInTheDocument();
    expect(within(finding).queryByText("Weak")).not.toBeInTheDocument();
    expect(within(finding).queryByText("Info")).not.toBeInTheDocument();
  });

  it("13. findings are ordered by strength", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);
    await screen.findByTestId("diagnostics-analysis");

    const articles = screen.getAllByTestId(/^finding-/);
    const ids = articles.map((el) => el.getAttribute("data-testid"));
    expect(ids).toEqual([
      "finding-F-TRIAGE",
      "finding-F-BACKLOG",
      "finding-F-INSUFF",
    ]);
  });

  it("14. validation questions are marked Template question", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(makeDiagnosticsResponse())
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const questionsSection = await screen.findByLabelText(
      "Questions for client validation"
    );
    const badges = within(questionsSection).getAllByText("Template question");
    expect(badges).toHaveLength(2);
    expect(
      within(questionsSection).getByText(
        /What are the agreed first-response SLA targets\?/i
      )
    ).toBeInTheDocument();
  });

  it("15. error state offers retry and recovers", async () => {
    const user = userEvent.setup();
    let calls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      calls += 1;
      if (calls === 1) {
        return jsonResponse({ detail: "Temporary analysis error" }, 500);
      }
      return jsonResponse(makeDiagnosticsResponse());
    });

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    const alert = await screen.findByRole("alert");
    expect(
      within(alert).getByText(/Temporary analysis error/i)
    ).toBeInTheDocument();

    await user.click(within(alert).getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByTestId("diagnostics-analysis")).toBeInTheDocument();
    });
    expect(calls).toBe(2);
  });

  it("16. a dataset with no valid rows shows the empty analysis state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        makeDiagnosticsResponse({
          scope_summary: {
            total_rows: 5,
            rows_valid_for_all_metrics: 0,
            excluded_by_scope: {
              all_metrics: 5,
              response_metrics: 5,
              resolution_metrics: 5,
              triage_metrics: 5,
            },
          },
          findings: [],
        })
      )
    );

    render(<DiagnosticsAnalysis engagementId={1} datasetId={10} />);

    await screen.findByText(/No valid rows available for analysis/i);
    expect(screen.queryByTestId("diagnostics-analysis")).not.toBeInTheDocument();
  });

  it("renders analysis on DiagnosticsPage when a dataset is present", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/engagements")) {
        return jsonResponse([ENGAGEMENT]);
      }
      if (url.endsWith("/api/engagements/1/datasets")) {
        return jsonResponse([SAMPLE_DATASET]);
      }
      if (url.includes("/api/engagements/1/datasets/10/diagnostics")) {
        return jsonResponse(makeDiagnosticsResponse());
      }
      if (url.includes("/api/engagements/1/datasets/10/rows")) {
        return jsonResponse({ total: 0, limit: 25, offset: 0, rows: [] });
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    await screen.findByTestId("diagnostics-analysis");
    expect(
      screen.getByRole("navigation", { name: "Diagnostics sections" })
    ).toBeInTheDocument();
  });
});
