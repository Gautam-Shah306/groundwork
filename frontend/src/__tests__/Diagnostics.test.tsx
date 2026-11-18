import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import type {
  DatasetRecord,
  DatasetRowsPage,
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
    checks: [
      {
        code: "duplicate_ticket_id",
        severity: "warning",
        count: 3,
        affects: ["all_metrics"],
        message: "Duplicate ticket_id detected.",
        recommended_action: "Deduplicate ticket exports by ticket_id.",
        examples: [
          { row_id: 1998, ticket_id: "KL-000101" },
          { row_id: 1999, ticket_id: "KL-000202" },
        ],
      },
      {
        code: "unknown_category",
        severity: "warning",
        count: 6,
        affects: ["all_metrics"],
        message: "Category is outside taxonomy.",
        recommended_action: "Map category to config/queues.yaml.",
        examples: [{ row_id: 50, ticket_id: "KL-000050" }],
      },
      {
        code: "missing_assignment",
        severity: "warning",
        count: 0,
        affects: ["triage_metrics"],
        message: "Only one of assigned_at or assigned_agent is present.",
        recommended_action: "Export both assignment fields.",
        examples: [],
      },
    ],
  },
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockDiagnosticsApi(options: {
  engagements?: Engagement[];
  datasets?: DatasetRecord[];
  onUpload?: () => Promise<Response> | Response;
  onSample?: () => Promise<Response> | Response;
  onRows?: (url: string) => Promise<Response> | Response;
  onDelete?: (id: number) => Promise<Response> | Response;
}) {
  let datasets = [...(options.datasets ?? [])];

  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/api/health")) {
      return jsonResponse({
        status: "ok",
        version: "0.1.0",
        llm_configured: false,
        database_url_scheme: "sqlite",
      });
    }

    if (url.endsWith("/api/engagements") && method === "GET") {
      return jsonResponse(options.engagements ?? [ENGAGEMENT]);
    }

    if (url.match(/\/api\/engagements\/\d+\/datasets\/sample$/) && method === "POST") {
      if (options.onSample) {
        return options.onSample();
      }
      datasets = [SAMPLE_DATASET, ...datasets];
      return jsonResponse(SAMPLE_DATASET, 201);
    }

    if (url.match(/\/api\/engagements\/\d+\/datasets\/\d+\/rows/)) {
      if (options.onRows) {
        return options.onRows(url);
      }
      const emptyPage: DatasetRowsPage = {
        dataset_id: 10,
        flag: "duplicate_ticket_id",
        page: 1,
        page_size: 25,
        total: 0,
        items: [],
      };
      return jsonResponse(emptyPage, 200);
    }

    const deleteMatch = url.match(/\/api\/engagements\/\d+\/datasets\/(\d+)$/);
    if (deleteMatch && method === "DELETE") {
      const id = Number(deleteMatch[1]);
      if (options.onDelete) {
        return options.onDelete(id);
      }
      datasets = datasets.filter((d) => d.id !== id);
      return new Response(null, { status: 204 });
    }

    if (url.match(/\/api\/engagements\/\d+\/datasets$/) && method === "POST") {
      if (options.onUpload) {
        return options.onUpload();
      }
      const uploaded: DatasetRecord = {
        ...SAMPLE_DATASET,
        id: 20,
        filename: "uploaded.csv",
        is_sample: false,
      };
      datasets = [uploaded, ...datasets];
      return jsonResponse(uploaded, 201);
    }

    if (url.match(/\/api\/engagements\/\d+\/datasets$/) && method === "GET") {
      return jsonResponse(datasets);
    }

    return jsonResponse({ detail: "Not found" }, 404);
  });
}

describe("Diagnostics data screen", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("diagnostics shows the engagement empty state when none selected", async () => {
    mockDiagnosticsApi({ engagements: [] });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("No engagement selected")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /Go to Engagements/i })).toHaveAttribute(
      "href",
      "/engagements"
    );
  });

  it("diagnostics shows the dropzone empty state with limits and the sample action", async () => {
    mockDiagnosticsApi({ engagements: [ENGAGEMENT], datasets: [] });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Upload support ticket CSV file/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Max 10 MB · Max 50,000 rows/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Load sample dataset" })
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic demonstration data")).toBeInTheDocument();
  });

  it("choosing a file uploads it and shows the progress phases", async () => {
    let resolveUpload!: (response: Response) => void;
    const uploadPromise = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });

    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [],
      onUpload: () => uploadPromise,
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const input = await screen.findByLabelText("CSV file input");
    const file = new File(["ticket_id\nKL-1\n"], "ops.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByRole("progressbar", { name: "Dataset upload progress" })
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Uploading")).toBeInTheDocument();
    expect(screen.getByText("Validating")).toBeInTheDocument();
    expect(screen.getByText("Saving")).toBeInTheDocument();

    resolveUpload(
      jsonResponse({ ...SAMPLE_DATASET, id: 21, filename: "ops.csv", is_sample: false }, 201)
    );

    await waitFor(() => {
      expect(screen.getByText(/Uploaded "ops\.csv"/i)).toBeInTheDocument();
    });
  });

  it("success message appears only after the API succeeds", async () => {
    let resolveUpload!: (response: Response) => void;
    const uploadPromise = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });

    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [],
      onUpload: () => uploadPromise,
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const input = await screen.findByLabelText("CSV file input");
    const file = new File(["ticket_id\nKL-1\n"], "pending.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("progressbar")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Uploaded "pending\.csv"/i)).not.toBeInTheDocument();

    resolveUpload(
      jsonResponse({ ...SAMPLE_DATASET, id: 22, filename: "pending.csv", is_sample: false }, 201)
    );

    await waitFor(() => {
      expect(screen.getByText(/Uploaded "pending\.csv"/i)).toBeInTheDocument();
    });
  });

  it("upload error shows the actionable message and keeps the file name", async () => {
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [],
      onUpload: () =>
        jsonResponse(
          { detail: { message: "Missing required column(s): category." } },
          422
        ),
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const input = await screen.findByLabelText("CSV file input");
    const file = new File(["bad\n1\n"], "broken_export.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByText("Missing required column(s): category.")
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/broken_export\.csv/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("sample load shows the synthetic data marker", async () => {
    mockDiagnosticsApi({ engagements: [ENGAGEMENT], datasets: [] });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await user.click(
      await screen.findByRole("button", { name: "Load sample dataset" })
    );

    await waitFor(() => {
      expect(screen.getByText("Synthetic data")).toBeInTheDocument();
    });
    expect(screen.getByText("Synthetic demonstration data")).toBeInTheDocument();
    expect(screen.getByText("sample_tickets.csv")).toBeInTheDocument();
  });

  it("validation table renders severity as text, counts right-aligned", async () => {
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Observed fact")).toBeInTheDocument();
    });

    const table = screen.getByRole("table", {
      name: "Data-quality validation checks",
    });
    expect(within(table).getAllByText("Warning").length).toBeGreaterThan(0);

    const countHeader = within(table).getByRole("columnheader", {
      name: "Rows affected",
    });
    const countCell = within(table).getByRole("cell", { name: "3" });
    expect(countHeader.className).toContain("text-right");
    expect(countCell.className).toContain("text-right");
    expect(countCell.className).toContain("tabular-nums");
  });

  it("rows-usable statement shows valid and excluded counts per scope", async () => {
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
    });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/1,991 of 2,000/i)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/excluded from response metrics/i)
    ).toBeInTheDocument();
    expect(screen.getByText("29")).toBeInTheDocument();
    expect(screen.getByText("22")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
  });

  it("passed checks are hidden until the toggle is on", async () => {
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("duplicate_ticket_id")).toBeInTheDocument();
    });
    expect(screen.queryByText("missing_assignment")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText(/Show passed checks/i));

    expect(screen.getByText("missing_assignment")).toBeInTheDocument();
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("expanding a check shows example rows", async () => {
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("duplicate_ticket_id")).toBeInTheDocument();
    });
    expect(screen.queryByText(/KL-000101/)).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "Toggle examples for duplicate_ticket_id",
      })
    );

    expect(screen.getByText(/Row #1998 · KL-000101/)).toBeInTheDocument();
    expect(screen.getByText(/Row #1999 · KL-000202/)).toBeInTheDocument();
  });

  it("clicking a check shows the paginated drill-down with its empty and error states", async () => {
    let mode: "empty" | "error" = "empty";
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
      onRows: () => {
        if (mode === "error") {
          return jsonResponse({ detail: "Rows query failed" }, 500);
        }
        return jsonResponse({
          dataset_id: 10,
          flag: "duplicate_ticket_id",
          page: 1,
          page_size: 25,
          total: 0,
          items: [],
        });
      },
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await user.click(
      await screen.findByRole("button", { name: "duplicate_ticket_id" })
    );

    await waitFor(() => {
      expect(screen.getByText("No flagged rows found")).toBeInTheDocument();
    });

    mode = "error";
    await user.click(screen.getByRole("button", { name: "unknown_category" }));

    await waitFor(() => {
      expect(screen.getByText("Rows query failed")).toBeInTheDocument();
    });
  });

  it("delete dataset requires confirmation", async () => {
    const fetchSpy = mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await user.click(
      await screen.findByRole("button", { name: "Delete dataset" })
    );
    expect(
      screen.getByRole("button", { name: "Confirm delete" })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      fetchSpy.mock.calls.filter(
        ([, init]) => (init?.method ?? "GET").toUpperCase() === "DELETE"
      )
    ).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Delete dataset" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => {
      expect(
        screen.getByText('Deleted dataset "sample_tickets.csv".')
      ).toBeInTheDocument();
    });
  });

  it("dropzone is keyboard operable (Enter/Space opens the file chooser)", async () => {
    mockDiagnosticsApi({ engagements: [ENGAGEMENT], datasets: [] });

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const dropzone = await screen.findByRole("button", {
      name: /Upload support ticket CSV file/i,
    });
    const fileInput = screen.getByLabelText("CSV file input") as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, "click");

    dropzone.focus();
    fireEvent.keyDown(dropzone, { key: "Enter" });
    fireEvent.keyDown(dropzone, { key: " " });

    expect(clickSpy).toHaveBeenCalledTimes(2);
  });

  it("cell content with angle brackets renders as text", async () => {
    const xssPayload = "<script>alert('xss')</script>";
    mockDiagnosticsApi({
      engagements: [ENGAGEMENT],
      datasets: [SAMPLE_DATASET],
      onRows: () =>
        jsonResponse({
          dataset_id: 10,
          flag: "unknown_category",
          page: 1,
          page_size: 25,
          total: 1,
          items: [
            {
              row_id: 50,
              ticket_id: xssPayload,
              engagement_id: 1,
              dataset_id: 10,
              created_at: "2026-09-10T04:30:00Z",
              assigned_at: null,
              first_response_at: null,
              resolved_at: null,
              category: "<b>billing_misc</b>",
              priority: "low",
              queue: "General",
              assigned_agent: null,
              status: "resolved",
              channel: "email",
              reassignment_count: 0,
              customer_id: "CUST-1",
              is_valid: false,
              validation_flags: [{ code: "unknown_category", affects: ["all_metrics"] }],
            },
          ],
        }),
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await user.click(
      await screen.findByRole("button", { name: "unknown_category" })
    );

    await waitFor(() => {
      expect(screen.getByText(xssPayload)).toBeInTheDocument();
    });
    expect(screen.getByText("<b>billing_misc</b>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });
});
