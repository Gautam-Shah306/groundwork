import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import {
  AssistantPanel,
  STARTER_QUESTIONS,
} from "../components/diagnostics/AssistantPanel";
import type {
  AssistantRun,
  DatasetRecord,
  Engagement,
} from "../lib/api";

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

function makeRun(overrides: Partial<AssistantRun> = {}): AssistantRun {
  return {
    id: 42,
    engagement_id: 1,
    dataset_id: 10,
    question: "Why are customers waiting so long?",
    status: "completed",
    answer_status: "structured",
    answer_blocks: [
      {
        type: "finding",
        text: "Median first-response time is 6.07 hours across 1,971 tickets.",
        evidence_call_ids: ["c1"],
      },
      {
        type: "hypothesis",
        text: "Manual queue assignment may delay initial agent pickup.",
        evidence_call_ids: [],
      },
      {
        type: "recommended_next_step",
        text: "Validate current triage assignment workflow with team leads.",
        evidence_call_ids: [],
      },
      {
        type: "clarifying_question",
        text: "Are SLA targets differentiated by channel?",
        evidence_call_ids: [],
      },
      {
        type: "limitation",
        text: "29 rows were excluded from response metrics due to timestamp anomalies.",
        evidence_call_ids: ["c1"],
      },
    ],
    tool_trace: [
      {
        call_id: "c1",
        tool: "get_response_metrics",
        args: { metric: "first_response_time" },
        ok: true,
        data: {
          metric_id: "first_response_time",
          title: "First-response time",
          definition: "Elapsed hours from created_at to first_response_at.",
          scope: "response_metrics",
          n_included: 1971,
          n_excluded: 29,
          exclusions: { first_response_before_created: 8 },
          data: { median: 6.07, n: 1971 },
        },
        error: null,
        duration_ms: 14,
      },
    ],
    warnings: [],
    error: null,
    model: "gemini-2.5-flash",
    round_trips: 2,
    started_at: "2026-11-18T11:00:00Z",
    finished_at: "2026-11-18T11:00:03Z",
    duration_ms: 3100,
    ...overrides,
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function flushMicrotasks(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
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
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("AssistantPanel & Diagnostics integration", () => {
  it("1. panel renders on Diagnostics when a dataset exists and can be collapsed and expanded", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements")) {
        return jsonResponse([ENGAGEMENT]);
      }
      if (url.endsWith("/api/engagements/1/datasets")) {
        return jsonResponse([SAMPLE_DATASET]);
      }
      if (url.includes("/api/engagements/1/assistant/runs")) {
        return jsonResponse([]);
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    const panel = await screen.findByTestId("assistant-panel");
    expect(within(panel).getByText("Investigation assistant")).toBeInTheDocument();

    const collapseBtn = within(panel).getByRole("button", {
      name: "Collapse investigation assistant",
    });
    await user.click(collapseBtn);

    expect(screen.queryByTestId("assistant-panel")).not.toBeInTheDocument();
    const collapsed = screen.getByTestId("assistant-panel-collapsed");
    const expandBtn = within(collapsed).getByRole("button", {
      name: "Expand investigation assistant",
    });
    await user.click(expandBtn);

    expect(screen.getByTestId("assistant-panel")).toBeInTheDocument();
  });

  it("2. panel is absent when there is no dataset", async () => {
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
    expect(screen.queryByTestId("assistant-panel")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("assistant-panel-collapsed")
    ).not.toBeInTheDocument();
  });

  it("3. not-configured state shows the actionable message and disables input", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: false,
          database_url_scheme: "sqlite",
        });
      }
      if (url.includes("/assistant/runs")) {
        return jsonResponse([]);
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const banner = await screen.findByTestId("assistant-not-configured");
    expect(within(banner).getByText(/LLM_API_KEY/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Ask about this dataset")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Investigate" })).toBeDisabled();
    for (const chip of STARTER_QUESTIONS) {
      expect(screen.getByRole("button", { name: chip })).toBeDisabled();
    }
  });

  it("4. starter question fills the field and submits", async () => {
    const user = userEvent.setup();
    let postedBody: Record<string, unknown> | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        postedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        return jsonResponse({ run_id: 77, status: "running" }, 202);
      }
      if (url.includes("/api/engagements/1/assistant/runs?limit=")) {
        return jsonResponse([]);
      }
      return jsonResponse(makeRun({ id: 77, status: "running", tool_trace: [] }));
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const chip = screen.getByRole("button", {
      name: "Which categories get reassigned most?",
    });
    await user.click(chip);

    await waitFor(() => {
      expect(postedBody).toEqual({
        question: "Which categories get reassigned most?",
        dataset_id: 10,
      });
    });
    expect(screen.getByLabelText("Ask about this dataset")).toHaveValue(
      "Which categories get reassigned most?"
    );
  });

  it("5. submit is disabled while a run is active and while the field is empty", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(
          makeRun({ status: "running", tool_trace: [], answer_blocks: [] })
        );
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    const textarea = screen.getByLabelText("Ask about this dataset");
    const submitBtn = screen.getByRole("button", { name: "Investigate" });
    expect(submitBtn).toBeDisabled();

    fireEvent.change(textarea, { target: { value: "Is backlog growing?" } });
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);
    await act(async () => {
      await Promise.resolve();
    });

    expect(
      screen.getByRole("button", { name: "Investigating..." })
    ).toBeDisabled();
  });

  it("6. live activity list updates as polling returns new trace items", async () => {
    vi.useFakeTimers();
    let pollCount = 0;

    const traceItem1 = makeRun().tool_trace[0];
    const traceItem2 = {
      call_id: "c2",
      tool: "get_backlog_analysis",
      args: {},
      ok: true,
      data: {
        metric_id: "backlog_ageing",
        definition: "Open backlog age buckets.",
        scope: "all_metrics",
        n_included: 1991,
        n_excluded: 9,
        exclusions: {},
        data: { total_open_backlog: 272 },
      },
      error: null,
      duration_ms: 9,
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        pollCount += 1;
        if (pollCount === 1) {
          return jsonResponse(
            makeRun({
              status: "running",
              tool_trace: [traceItem1],
              answer_blocks: [],
            })
          );
        }
        return jsonResponse(
          makeRun({
            status: "completed",
            tool_trace: [traceItem1, traceItem2],
          })
        );
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.queryByTestId("activity-item-c1")).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByTestId("activity-item-c1")).toBeInTheDocument();
    expect(screen.queryByTestId("activity-item-c2")).not.toBeInTheDocument();
    expect(screen.queryByTestId("assistant-findings")).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByTestId("activity-item-c2")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-findings")).toBeInTheDocument();
  });

  it("7. tool call item expands to show arguments and result summary", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(makeRun());
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const item = screen.getByTestId("activity-item-c1");
    expect(screen.queryByTestId("activity-detail-c1")).not.toBeInTheDocument();

    const toggle = within(item).getByRole("button");
    fireEvent.click(toggle);

    const detail = screen.getByTestId("activity-detail-c1");
    expect(within(detail).getByText(/first_response_time/)).toBeInTheDocument();
    expect(
      within(detail).getByText(/Elapsed hours from created_at/i)
    ).toBeInTheDocument();
    expect(within(detail).getByText(/1,971/)).toBeInTheDocument();
    expect(
      within(detail).getByText(/first_response_before_created: 8/)
    ).toBeInTheDocument();
  });

  it("8. completion is announced only after the run status is completed", async () => {
    vi.useFakeTimers();
    let poll = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        poll += 1;
        return jsonResponse(
          poll === 1 ? makeRun({ status: "running", answer_blocks: [] }) : makeRun()
        );
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const liveRegion = screen.getByTestId("assistant-live-region");
    expect(liveRegion.textContent).toBe("");
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(liveRegion.textContent).toMatch(/Investigation completed/i);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("9. answer blocks render with the correct TypeLabels", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(makeRun());
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const b0 = screen.getByTestId("answer-block-0");
    expect(within(b0).getByText("Observed fact")).toBeInTheDocument();

    const b1 = screen.getByTestId("answer-block-1");
    expect(within(b1).getByText("Hypothesis")).toBeInTheDocument();
    expect(within(b1).getByText("Needs validation")).toBeInTheDocument();

    const b2 = screen.getByTestId("answer-block-2");
    expect(within(b2).getByText("AI recommendation")).toBeInTheDocument();

    const b3 = screen.getByTestId("answer-block-3");
    expect(within(b3).getByText("Clarifying question")).toBeInTheDocument();

    const b4 = screen.getByTestId("answer-block-4");
    expect(within(b4).getByText("Limitation")).toBeInTheDocument();
  });

  it("10. evidence chip opens the referenced tool call", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(makeRun());
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.queryByTestId("activity-detail-c1")).not.toBeInTheDocument();

    const block0 = screen.getByTestId("answer-block-0");
    const chip = within(block0).getByRole("button", {
      name: /c1 · get_response_metrics/i,
    });
    fireEvent.click(chip);

    expect(screen.getByTestId("activity-detail-c1")).toBeInTheDocument();
  });

  it("11. grounding warnings and Unsupported statement markers are visible next to their block", async () => {
    vi.useFakeTimers();
    const warnedRun = makeRun({
      answer_blocks: [
        {
          type: "finding",
          text: "Median delay reaches 99.9 hours because of staffing.",
          evidence_call_ids: [],
        },
      ],
      warnings: [
        {
          block_index: 0,
          code: "unsupported_finding",
          message: "This finding does not cite any supporting tool call.",
          details: {},
        },
        {
          block_index: 0,
          code: "ungrounded_number",
          message: "Figure '99.9 hours' could not be verified against cited tool outputs.",
          details: { number: "99.9 hours" },
        },
      ],
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(warnedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const block0 = screen.getByTestId("answer-block-0");
    expect(
      within(block0).getAllByText("Unsupported statement").length
    ).toBeGreaterThanOrEqual(1);
    expect(within(block0).getByText("Ungrounded figure")).toBeInTheDocument();
    expect(
      within(block0).getByText(/Figure '99\.9 hours' could not be verified/i)
    ).toBeInTheDocument();
    // Content is preserved alongside warnings
    expect(
      within(block0).getByText(/Median delay reaches 99\.9 hours/i)
    ).toBeInTheDocument();
  });

  it("12. unstructured result is labelled Unverified response and not shown as findings", async () => {
    vi.useFakeTimers();
    const unstructuredRun = makeRun({
      answer_status: "unstructured",
      answer_blocks: [
        {
          type: "unverified",
          text: "Raw prose output that could not be parsed as JSON.",
          evidence_call_ids: [],
        },
      ],
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 42, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/42")) {
        return jsonResponse(unstructuredRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Why are customers waiting so long?" })
    );
    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const box = screen.getByTestId("assistant-unverified-response");
    expect(within(box).getByText("Unverified response")).toBeInTheDocument();
    expect(
      within(box).getByText(/Raw prose output that could not be parsed/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("Observed fact")).not.toBeInTheDocument();
  });

  it("13. error states show actionable text, keep the question, and allow retry", async () => {
    const user = userEvent.setup();
    let attempts = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        attempts += 1;
        if (attempts === 1) {
          return jsonResponse(
            {
              detail: {
                code: "run_in_progress",
                message: "An investigation is already running for this engagement.",
              },
            },
            409
          );
        }
        return jsonResponse({ run_id: 99, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/99")) {
        return jsonResponse(makeRun({ id: 99 }));
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const textarea = screen.getByLabelText("Ask about this dataset");
    await user.type(textarea, "Why did evening delays spike?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    const errBox = await screen.findByTestId("assistant-error");
    expect(
      within(errBox).getByText(/already running for this engagement/i)
    ).toBeInTheDocument();
    // Question is preserved
    expect(textarea).toHaveValue("Why did evening delays spike?");

    await user.click(within(errBox).getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(attempts).toBe(2);
    });
  });

  it("14. previous investigations list opens a stored run", async () => {
    const user = userEvent.setup();
    const storedRun = makeRun({
      id: 12,
      question: "Stored backlog investigation",
      answer_blocks: [
        {
          type: "finding",
          text: "Open backlog stands at 272 tickets.",
          evidence_call_ids: ["c1"],
        },
      ],
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.includes("/api/engagements/1/assistant/runs?limit=")) {
        return jsonResponse([storedRun]);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/12")) {
        return jsonResponse(storedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const historySection = await screen.findByLabelText("Previous investigations");
    const runBtn = within(historySection).getByRole("button", {
      name: /Stored backlog investigation/i,
    });
    await user.click(runBtn);

    await screen.findByText(/Open backlog stands at 272 tickets/i);
  });

  it("15. keyboard: panel toggle, chips, textarea and submit are operable and have accessible names", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse investigation assistant",
    });
    collapseBtn.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("assistant-panel-collapsed")).toBeInTheDocument();

    const expandBtn = screen.getByRole("button", {
      name: "Expand investigation assistant",
    });
    expandBtn.focus();
    await user.keyboard(" ");
    expect(screen.getByTestId("assistant-panel")).toBeInTheDocument();

    const textarea = screen.getByRole("textbox", {
      name: "Ask about this dataset",
    });
    expect(textarea).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Investigate" })
    ).toBeInTheDocument();
    for (const chip of STARTER_QUESTIONS) {
      expect(screen.getByRole("button", { name: chip })).toBeInTheDocument();
    }
  });

  it("16. the AI-generated disclosure text is present", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);
    await flushMicrotasks();

    expect(
      screen.getByText(
        "AI-generated. Figures come from the deterministic metrics shown as evidence."
      )
    ).toBeInTheDocument();
  });

  it("17. quota exhausted error shows the actionable message and keeps the question", async () => {
    const user = userEvent.setup();
    const failedRun = makeRun({
      id: 50,
      question: "Why are triage queues overflowing?",
      status: "failed",
      error: {
        code: "llm_quota_exhausted",
        message:
          "The LLM provider reports that credits or the daily limit are exhausted for this API key's project. Check billing and quota, wait for the limit to reset, or use a different key.",
      },
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 50, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/50")) {
        return jsonResponse(failedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const textarea = screen.getByLabelText("Ask about this dataset");
    await user.type(textarea, "Why are triage queues overflowing?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    const errBox = await screen.findByTestId(
      "assistant-run-error",
      {},
      { timeout: 3000 }
    );
    expect(
      within(errBox).getByText(/credits or the daily limit are exhausted/i)
    ).toBeInTheDocument();
    expect(textarea).toHaveValue("Why are triage queues overflowing?");
    expect(within(errBox).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("18. model not found error shows the actionable message with a retry action", async () => {
    const user = userEvent.setup();
    const failedRun = makeRun({
      id: 51,
      question: "Are first response metrics within SLA?",
      status: "failed",
      error: {
        code: "llm_model_not_found",
        message:
          "The configured LLM_MODEL was not found by the provider. Check the model name in your environment settings.",
      },
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 51, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/51")) {
        return jsonResponse(failedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const textarea = screen.getByLabelText("Ask about this dataset");
    await user.type(textarea, "Are first response metrics within SLA?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    const errBox = await screen.findByTestId(
      "assistant-run-error",
      {},
      { timeout: 3000 }
    );
    expect(
      within(errBox).getByText(/configured LLM_MODEL was not found/i)
    ).toBeInTheDocument();
    const retryBtn = within(errBox).getByRole("button", { name: "Retry" });
    expect(retryBtn).toBeInTheDocument();
  });

  it("19. request too large error shows the actionable message", async () => {
    const user = userEvent.setup();
    const failedRun = makeRun({
      id: 52,
      question: "Provide exhaustive summary of all categories",
      status: "failed",
      error: {
        code: "llm_request_too_large",
        message:
          "The request exceeded the provider's size or token limit for this model.",
      },
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        return jsonResponse({ run_id: 52, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/52")) {
        return jsonResponse(failedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const textarea = screen.getByLabelText("Ask about this dataset");
    await user.type(textarea, "Provide exhaustive summary of all categories");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    const errBox = await screen.findByTestId(
      "assistant-run-error",
      {},
      { timeout: 3000 }
    );
    expect(
      within(errBox).getByText(/request exceeded the provider's size or token limit/i)
    ).toBeInTheDocument();
  });

  it("20. tool call failed error offers an immediate retry and keeps the question", async () => {
    const user = userEvent.setup();
    let postCount = 0;
    const failedRun = makeRun({
      id: 53,
      question: "Which categories get reassigned most?",
      status: "failed",
      error: {
        code: "llm_tool_call_failed",
        message:
          "The model produced an invalid tool call. Try the question again.",
      },
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.endsWith("/api/engagements/1/assistant/runs") && init?.method === "POST") {
        postCount += 1;
        return jsonResponse({ run_id: 53, status: "running" }, 202);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/53")) {
        return jsonResponse(failedRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const textarea = screen.getByLabelText("Ask about this dataset");
    await user.type(textarea, "Which categories get reassigned most?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    const errBox = await screen.findByTestId(
      "assistant-run-error",
      {},
      { timeout: 3000 }
    );
    expect(
      within(errBox).getByText(/model produced an invalid tool call/i)
    ).toBeInTheDocument();
    expect(textarea).toHaveValue("Which categories get reassigned most?");

    const retryBtn = within(errBox).getByRole("button", { name: "Retry" });
    await user.click(retryBtn);
    await waitFor(() => {
      expect(postCount).toBe(2);
    });
  });

  it("21. unknown answer status renders safely without throwing", async () => {
    const user = userEvent.setup();
    const unknownStatusRun = makeRun({
      id: 99,
      question: "Unknown status investigation",
      answer_status: "unsupported" as any,
      answer_blocks: [
        {
          type: "finding",
          text: "Some finding text with unknown status.",
          evidence_call_ids: [],
        },
      ],
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.includes("/api/engagements/1/assistant/runs?limit=")) {
        return jsonResponse([unknownStatusRun]);
      }
      if (url.endsWith("/api/engagements/1/assistant/runs/99")) {
        return jsonResponse(unknownStatusRun);
      }
      return jsonResponse([]);
    });

    render(<AssistantPanel engagementId={1} datasetId={10} />);

    const historySection = await screen.findByLabelText("Previous investigations");
    const runBtn = within(historySection).getByRole("button", {
      name: /Unknown status investigation/i,
    });
    await user.click(runBtn);

    expect(await screen.findByText("Some finding text with unknown status.")).toBeInTheDocument();
  });
});
