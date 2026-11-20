import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EngagementProvider } from "../context/EngagementContext";
import {
  RunControls,
  ProgressCard,
  ResultsSummary,
  ConfusionMatrix,
  SlicesTable,
  FailureCasesList,
  RunHistory,
} from "../components/evaluation";
import { PrototypesPage } from "../pages/PrototypesPage";
import { formatAuditSentence } from "../lib/format";
import type { AuditLogEntry, EvalResults, EvalRunSummary } from "../lib/api";

const MOCK_RESULTS: EvalResults = {
  summary: {
    total_tickets: 150,
    completed: 150,
    failed: 0,
    category_accuracy: 0.8667,
    category_accuracy_completed: 0.8667,
    category_accuracy_wilson: [0.803, 0.912],
    lenient_category_accuracy: 0.92,
    priority_accuracy: 0.9333,
    queue_accuracy: 0.92,
    reviewer_change_proxy: 0.14,
    category_accuracy_pct: 86.7,
    priority_accuracy_pct: 93.3,
    queue_accuracy_pct: 92.0,
    reviewer_change_proxy_pct: 14.0,
  },
  per_category: {
    order_tracking: {
      support: 25,
      predicted_count: 24,
      precision: 0.9167,
      recall: 0.88,
      f1: 0.898,
    },
    damaged_item: {
      support: 20,
      predicted_count: 20,
      precision: 0.9,
      recall: 0.9,
      f1: 0.9,
    },
  },
  macro_f1: 0.899,
  category_confusion_matrix: {
    order_tracking: { order_tracking: 22, damaged_item: 2, no_prediction: 0 },
    damaged_item: { order_tracking: 1, damaged_item: 18, no_prediction: 1 },
  },
  priority_metrics: {
    priority_accuracy: 0.9333,
    confusion_matrix: {
      high: { high: 40, medium: 2, low: 0, no_prediction: 0 },
      medium: { high: 1, medium: 50, low: 2, no_prediction: 0 },
      low: { high: 0, medium: 5, low: 50, no_prediction: 0 },
    },
    under_prioritised: 4,
    over_prioritised: 6,
    missed_high: { count: 2, rate: 0.0476 },
    truth_high_no_prediction: { count: 0, rate: 0.0 },
    priority_errors_by_cause: {
      signals_exact_but_priority_wrong: 0,
      signals_missed: 4,
      signals_spurious: 6,
      signals_both: 0,
      model_failure: 0,
    },
  },
  signals_metrics: {
    micro_precision: 0.92,
    micro_recall: 0.89,
    micro_f1: 0.9048,
    exact_set_match_rate: 0.84,
    per_signal: {},
  },
  slices: [
    { name: "en", count: 90, category_accuracy: 0.8889, priority_accuracy: 0.9444, low_confidence: false },
    { name: "hinglish", count: 60, category_accuracy: 0.8333, priority_accuracy: 0.9167, low_confidence: false },
    { name: "is_ambiguous", count: 25, category_accuracy: 0.68, priority_accuracy: 0.88, low_confidence: true },
    { name: "short", count: 20, category_accuracy: 0.85, priority_accuracy: 0.9, low_confidence: true },
    { name: "urgency_or_delay", count: 45, category_accuracy: 0.8667, priority_accuracy: 0.9333, low_confidence: false },
  ],
  failure_cases: [
    {
      ticket_id: "EV-012",
      subject: "Broken table",
      body_snippet: "My dining table arrived split in two halves.",
      true_category: "damaged_item",
      predicted_category: "damaged_item",
      true_priority: "high",
      predicted_priority: "medium",
      true_signals: ["item_damaged_or_defective"],
      predicted_signals: [],
      reason: "High priority ticket under-prioritised to medium.",
    },
  ],
};

const MOCK_RUN: EvalRunSummary = {
  id: 1,
  engagement_id: 1,
  model: "openai/gpt-oss-20b",
  sample_size: 150,
  status: "completed",
  config: { sample_size: 150, drafts_sample: 0, model: "openai/gpt-oss-20b" },
  progress_done: 150,
  progress_total: 150,
  config_fingerprint: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  started_at: "2026-11-20T05:00:00Z",
  finished_at: "2026-11-20T05:05:00Z",
  created_at: "2026-11-20T05:00:00Z",
  usage: {
    prompt_tokens: 120000,
    completion_tokens: 30000,
    total_tokens: 150000,
    provider_calls: 150,
    estimated_cost_usd: null,
  },
  results: MOCK_RESULTS,
};

describe("Agent evaluation frontend components", () => {
  const MOCK_ENGAGEMENT = {
    id: 1,
    name: "Kora Living",
    client_name: "Kora",
    stage: "build",
    is_synthetic: true,
  };

  vi.spyOn(globalThis, "fetch").mockImplementation(async (url: any) => {
    const u = String(url);
    if (u.includes("/triage/proposals")) return new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }));
    if (u.includes("/evaluation/runs")) return new Response(JSON.stringify([]));
    if (u.includes("/health")) return new Response(JSON.stringify({ llm_configured: true, status: "ok" }));
    if (u.includes("/engagements")) return new Response(JSON.stringify([MOCK_ENGAGEMENT]));
    return new Response(JSON.stringify({}));
  });

  // 1. accessible tablist renders both tabs with correct aria roles and attributes
  it("accessible tablist renders both tabs with correct aria roles and attributes", async () => {
    render(
      <MemoryRouter initialEntries={["/prototypes"]}>
        <EngagementProvider>
          <PrototypesPage />
        </EngagementProvider>
      </MemoryRouter>
    );

    const tablist = await screen.findByRole("tablist", { name: /Prototypes views/i });
    expect(tablist).toBeInTheDocument();

    const triageTab = screen.getByRole("tab", { name: /Triage workspace/i });
    const evalTab = screen.getByRole("tab", { name: /Agent evaluation/i });

    expect(triageTab).toHaveAttribute("aria-selected", "true");
    expect(evalTab).toHaveAttribute("aria-selected", "false");
  });

  // 2. tab state switches via click and keyboard arrow navigation
  it("tab state switches via click and keyboard arrow navigation", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/prototypes"]}>
        <EngagementProvider>
          <PrototypesPage />
        </EngagementProvider>
      </MemoryRouter>
    );

    const triageTab = await screen.findByRole("tab", { name: /Triage workspace/i });
    const evalTab = screen.getByRole("tab", { name: /Agent evaluation/i });

    // Switch via click
    await user.click(evalTab);
    expect(evalTab).toHaveAttribute("aria-selected", "true");
    expect(triageTab).toHaveAttribute("aria-selected", "false");

    // Switch via ArrowLeft
    fireEvent.keyDown(evalTab, { key: "ArrowLeft" });
    expect(triageTab).toHaveAttribute("aria-selected", "true");
  });

  // 3. tab state preserves in URL query param (?tab=evaluation)
  it("tab state preserves in URL query param (?tab=evaluation)", async () => {
    render(
      <MemoryRouter initialEntries={["/prototypes?tab=evaluation"]}>
        <EngagementProvider>
          <PrototypesPage />
        </EngagementProvider>
      </MemoryRouter>
    );

    const evalTab = await screen.findByRole("tab", { name: /Agent evaluation/i });
    expect(evalTab).toHaveAttribute("aria-selected", "true");
  });

  // 4. run controls render sample size options (20, 50, 150 default)
  it("run controls render sample size options (20, 50, 150 default)", () => {
    render(<RunControls onStartRun={vi.fn()} isRunning={false} />);
    expect(screen.getByRole("radio", { name: /20 \(Smoke\)/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^50$/i })).toBeInTheDocument();
    const opt150 = screen.getByRole("radio", { name: /150 \(Full Test Set\)/i });
    expect(opt150).toBeInTheDocument();
    expect(opt150).toHaveAttribute("aria-checked", "true");
  });

  // 5. run controls render model name
  it("run controls render model name", () => {
    render(<RunControls onStartRun={vi.fn()} isRunning={false} configuredModel="meta-llama/llama-3-70b" />);
    expect(screen.getByText("meta-llama/llama-3-70b")).toBeInTheDocument();
  });

  // 6. run controls render draft toggle
  it("run controls render draft toggle", () => {
    render(<RunControls onStartRun={vi.fn()} isRunning={false} />);
    const checkbox = screen.getByLabelText(/Also check draft replies on first 21 tickets/i);
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();
  });

  // 7. run evaluation button disabled when run in progress
  it("run evaluation button disabled when run in progress", () => {
    render(<RunControls onStartRun={vi.fn()} isRunning={true} />);
    const btn = screen.getByRole("button", { name: /Evaluation Running/i });
    expect(btn).toBeDisabled();
  });

  // 8. run evaluation button disabled when LLM not configured
  it("run evaluation button disabled when LLM not configured", () => {
    render(<RunControls onStartRun={vi.fn()} isRunning={false} disabled={true} />);
    const btn = screen.getByRole("button", { name: /Run evaluation/i });
    expect(btn).toBeDisabled();
  });

  // 9. starting run triggers POST and renders progress card
  it("starting run triggers onStartRun with selected payload", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn().mockResolvedValue(undefined);
    render(<RunControls onStartRun={onStart} isRunning={false} configuredModel="openai/gpt-oss-20b" />);

    // Click 20 (smoke)
    await user.click(screen.getByRole("radio", { name: /20 \(Smoke\)/i }));
    // Check draft checkbox
    await user.click(screen.getByLabelText(/Also check draft replies/i));

    // Submit
    await user.click(screen.getByRole("button", { name: /Run evaluation/i }));
    expect(onStart).toHaveBeenCalledWith({
      sample_size: 20,
      drafts_sample: 21,
      model: "openai/gpt-oss-20b",
    });
  });

  // 10. progress card displays progress percentage and ticket count
  it("progress card displays progress percentage and ticket count", () => {
    const runningRun: EvalRunSummary = {
      ...MOCK_RUN,
      status: "running",
      progress_done: 45,
      progress_total: 150,
    };
    render(<ProgressCard run={runningRun} onResume={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Progress: 45 of 150 tickets \(30%\)/i)).toBeInTheDocument();
  });

  // 11. progress card shows pacing indicator
  it("progress card shows pacing indicator", () => {
    const runningRun: EvalRunSummary = { ...MOCK_RUN, status: "running" };
    render(<ProgressCard run={runningRun} onResume={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Pacing 2s/i)).toBeInTheDocument();
  });

  // 12. progress card shows estimated remaining time
  it("progress card shows estimated remaining time", () => {
    const runningRun: EvalRunSummary = {
      ...MOCK_RUN,
      status: "running",
      progress_done: 10,
      progress_total: 100,
    };
    render(<ProgressCard run={runningRun} onResume={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Est\. remaining:/i)).toBeInTheDocument();
  });

  // 13. paused run renders error banner and resume button
  it("paused run renders error banner and resume button", () => {
    const pausedRun: EvalRunSummary = {
      ...MOCK_RUN,
      status: "paused",
      error: { code: "interrupted", message: "Server restart detected" },
    };
    render(<ProgressCard run={pausedRun} onResume={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Run interrupted: interrupted/i)).toBeInTheDocument();
    expect(screen.getByText(/Server restart detected/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Resume/i })).toBeInTheDocument();
  });

  // 14. clicking resume triggers onResume
  it("clicking resume triggers onResume callback", async () => {
    const user = userEvent.setup();
    const onResume = vi.fn().mockResolvedValue(undefined);
    const pausedRun: EvalRunSummary = { ...MOCK_RUN, status: "paused" };
    render(<ProgressCard run={pausedRun} onResume={onResume} onCancel={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Resume/i }));
    expect(onResume).toHaveBeenCalledWith(pausedRun.id);
  });

  // 15. clicking cancel triggers onCancel
  it("clicking cancel triggers onCancel callback", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn().mockResolvedValue(undefined);
    render(<ProgressCard run={MOCK_RUN} onResume={vi.fn()} onCancel={onCancel} />);
    await user.click(screen.getByRole("button", { name: /Cancel run/i }));
    expect(onCancel).toHaveBeenCalledWith(MOCK_RUN.id);
  });

  // 16. completed run renders results summary with all 6 KPI tiles
  it("completed run renders results summary with all 6 KPI tiles", () => {
    render(<ResultsSummary run={MOCK_RUN} />);
    expect(screen.getByText(/Strict Category Acc\./i)).toBeInTheDocument();
    expect(screen.getByText("86.7%")).toBeInTheDocument();
    expect(screen.getByText(/Lenient Category Acc\./i)).toBeInTheDocument();
    expect(screen.getByText(/Priority Accuracy/i)).toBeInTheDocument();
    expect(screen.getByText("93.3%")).toBeInTheDocument();
    expect(screen.getByText(/Queue Routing Acc\./i)).toBeInTheDocument();
    expect(screen.getAllByText("92%")).toHaveLength(2);
    expect(screen.getByText(/Reviewer Change Proxy/i)).toBeInTheDocument();
    expect(screen.getByText("14%")).toBeInTheDocument();
  });

  // 17. strict accuracy tile displays Wilson interval in subtitle
  it("strict accuracy tile displays Wilson interval in subtitle", () => {
    render(<ResultsSummary run={MOCK_RUN} />);
    expect(screen.getByText(/Wilson 95%: \[80.3%, 91.2%\]/i)).toBeInTheDocument();
  });

  // 18. confusion matrix renders true categories as rows, predicted as columns + No prediction
  it("confusion matrix renders true categories as rows, predicted as columns + No prediction", () => {
    render(<ConfusionMatrix results={MOCK_RESULTS} />);
    expect(screen.getByText("True \\ Pred")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
    expect(screen.getAllByText("order_tracking").length).toBeGreaterThan(0);
    expect(screen.getAllByText("damaged_item").length).toBeGreaterThan(0);
  });

  // 19. confusion matrix highlights diagonal cells and off-diagonal non-zero errors
  it("confusion matrix highlights diagonal cells and off-diagonal non-zero errors", () => {
    const { container } = render(<ConfusionMatrix results={MOCK_RESULTS} />);
    // Diagonal styling
    const diagCells = container.querySelectorAll(".bg-accent\\/10");
    expect(diagCells.length).toBeGreaterThan(0);
    // Off-diagonal warning styling
    const offDiagCells = container.querySelectorAll(".bg-warning-soft");
    expect(offDiagCells.length).toBeGreaterThan(0);
  });

  // 20. per-category table renders precision, recall, F1, and macro-F1
  it("per-category table renders precision, recall, F1, and macro-F1", () => {
    render(<ConfusionMatrix results={MOCK_RESULTS} />);
    expect(screen.getByText(/Macro-averaged F1 Score/i)).toBeInTheDocument();
    expect(screen.getByText("89.9%")).toBeInTheDocument();
  });

  // 21. slices table renders all 5 slices with low-confidence flag for n < 30
  it("slices table renders all 5 slices with low-confidence flag for n < 30", () => {
    render(<SlicesTable slices={MOCK_RESULTS.slices} />);
    expect(screen.getByText("English tickets")).toBeInTheDocument();
    expect(screen.getByText("Hinglish tickets")).toBeInTheDocument();
    expect(screen.getByText("Ambiguous tickets")).toBeInTheDocument();
    expect(screen.getByText("Short tickets (<100 chars)")).toBeInTheDocument();
    expect(screen.getByText("Urgency / Delay tickets")).toBeInTheDocument();

    const lowFlags = screen.getAllByText("Low n (<30)");
    expect(lowFlags.length).toBe(2); // is_ambiguous (25) and short (20)
  });

  // 22. failure cases list renders up to 5 cases with comparison of true vs predicted
  it("failure cases list renders up to 5 cases with comparison of true vs predicted", () => {
    render(<FailureCasesList failureCases={MOCK_RESULTS.failure_cases} />);
    expect(screen.getByText(/#1 EV-012/i)).toBeInTheDocument();
    expect(screen.getByText(/High priority ticket under-prioritised to medium\./i)).toBeInTheDocument();
    expect(screen.getByText(/"My dining table arrived split in two halves\.…"/i)).toBeInTheDocument();
  });

  // 23. clicking view all failed tickets toggles the complete failure list
  it("clicking view all failed tickets toggles the complete failure list", async () => {
    const user = userEvent.setup();
    const onViewAll = vi.fn();
    render(
      <FailureCasesList
        failureCases={MOCK_RESULTS.failure_cases}
        onViewAllFailed={onViewAll}
        failedItems={[
          {
            id: 1,
            run_id: 1,
            ticket_id: "EV-012",
            status: "success",
            predicted_category: "damaged_item",
            predicted_priority: "medium",
            predicted_signals: [],
            flags: [],
            escalation: false,
            usage: {},
            duration_ms: 100,
            provider_calls: 1,
            created_at: "2026-11-20T05:00:00Z",
          },
        ]}
      />
    );

    const btn = screen.getByRole("button", { name: /View all failed tickets/i });
    await user.click(btn);
    expect(onViewAll).toHaveBeenCalled();
    expect(screen.getByText(/All Failed Evaluation Tickets \(1\)/i)).toBeInTheDocument();
  });

  // 24. run history renders past runs with view button that switches active display
  it("run history renders past runs with view button that switches active display", () => {
    const onSelect = vi.fn();
    render(<RunHistory runs={[MOCK_RUN]} selectedRunId={MOCK_RUN.id} onSelectRun={onSelect} />);
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("86.7%")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  // 25. formatAuditSentence formats evaluation audit actions correctly
  it("formatAuditSentence formats evaluation audit actions correctly", () => {
    const entries: AuditLogEntry[] = [
      { id: 1, engagement_id: 1, actor: "Operator", action: "eval_run_started", entity_type: "eval_run", entity_id: "1", details: {}, created_at: "2026-11-20T05:00:00Z" },
      { id: 2, engagement_id: 1, actor: "Operator", action: "eval_run_completed", entity_type: "eval_run", entity_id: "1", details: {}, created_at: "2026-11-20T05:05:00Z" },
      { id: 3, engagement_id: 1, actor: "Operator", action: "eval_run_paused", entity_type: "eval_run", entity_id: "1", details: {}, created_at: "2026-11-20T05:02:00Z" },
      { id: 4, engagement_id: 1, actor: "Operator", action: "eval_run_resumed", entity_type: "eval_run", entity_id: "1", details: {}, created_at: "2026-11-20T05:03:00Z" },
      { id: 5, engagement_id: 1, actor: "Operator", action: "eval_run_cancelled", entity_type: "eval_run", entity_id: "1", details: {}, created_at: "2026-11-20T05:04:00Z" },
    ];

    expect(formatAuditSentence(entries[0])).toBe("Operator started evaluation run #1");
    expect(formatAuditSentence(entries[1])).toBe("Operator completed evaluation run #1");
    expect(formatAuditSentence(entries[2])).toBe("Operator paused evaluation run #1");
    expect(formatAuditSentence(entries[3])).toBe("Operator resumed evaluation run #1");
    expect(formatAuditSentence(entries[4])).toBe("Operator cancelled evaluation run #1");
  });
});
