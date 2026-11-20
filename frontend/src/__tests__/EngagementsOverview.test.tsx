import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { ACTIVE_ENGAGEMENT_STORAGE_KEY } from "../context/EngagementContext";
import type { AuditLogEntry, Engagement, ProblemBrief } from "../lib/api";

const ENGAGEMENT_ONE: Engagement = {
  id: 1,
  name: "Kora Living: Customer support turnaround",
  client_name: "Kora Living",
  industry: "D2C home-goods retail",
  client_statement:
    "Our customer support team is overwhelmed. Customers are waiting too long for responses.",
  stage: "discover",
  is_synthetic: true,
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-18T08:00:00Z",
};

const ENGAGEMENT_TWO: Engagement = {
  id: 2,
  name: "Northwind: Returns queue review",
  client_name: "Northwind Home",
  industry: "Retail",
  client_statement: "Returns are piling up before weekend cutoffs.",
  stage: "diagnose",
  is_synthetic: true,
  created_at: "2026-11-18T09:00:00Z",
  updated_at: "2026-11-18T09:00:00Z",
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setupApiMock(options: {
  engagements?: Engagement[];
  brief?: ProblemBrief | null;
  activity?: AuditLogEntry[];
  onCreate?: (body: Record<string, unknown>) => Response;
  onDelete?: (id: number) => Response;
}) {
  let items = [...(options.engagements ?? [])];

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

    if (url.match(/\/api\/engagements\/\d+\/brief/)) {
      if (options.brief) {
        return jsonResponse(options.brief, 200);
      }
      return jsonResponse(
        { detail: "No problem brief exists for this engagement yet." },
        404
      );
    }

    if (url.match(/\/api\/engagements\/\d+\/activity/)) {
      return jsonResponse(options.activity ?? [], 200);
    }

    const deleteMatch = url.match(/\/api\/engagements\/(\d+)$/);
    if (deleteMatch && method === "DELETE") {
      const id = Number(deleteMatch[1]);
      if (options.onDelete) {
        return options.onDelete(id);
      }
      items = items.filter((item) => item.id !== id);
      return new Response(null, { status: 204 });
    }

    if (url.endsWith("/api/engagements") && method === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<
        string,
        unknown
      >;
      if (options.onCreate) {
        return options.onCreate(body);
      }
      const created: Engagement = {
        id: items.length + 10,
        name: String(body.name ?? ""),
        client_name: String(body.client_name ?? ""),
        industry: String(body.industry ?? ""),
        client_statement: String(body.client_statement ?? ""),
        stage: (body.stage as Engagement["stage"]) ?? "discover",
        is_synthetic: true,
        created_at: "2026-11-18T10:00:00Z",
        updated_at: "2026-11-18T10:00:00Z",
      };
      items = [...items, created];
      return jsonResponse(created, 201);
    }

    if (url.endsWith("/api/engagements") && method === "GET") {
      return jsonResponse(items, 200);
    }

    return jsonResponse({ detail: "Not found" }, 404);
  });
}

describe("Engagements and Overview pages", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("engagements page shows loading, then rows", async () => {
    let resolveList!: (response: Response) => void;
    const listPromise = new Promise<Response>((resolve) => {
      resolveList = resolve;
    });

    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/health")) {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            version: "0.1.0",
            llm_configured: false,
            database_url_scheme: "sqlite",
          })
        );
      }
      return listPromise;
    });

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Loading table data...")).toBeInTheDocument();

    resolveList(jsonResponse([ENGAGEMENT_ONE], 200));

    await waitFor(() => {
      expect(
        screen.getByRole("cell", { name: /Kora Living: Customer support turnaround/i })
      ).toBeInTheDocument();
    });
  });

  it("engagements page shows empty state when there are none", async () => {
    setupApiMock({ engagements: [] });

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("No engagements created yet")).toBeInTheDocument();
    });
  });

  it("engagements page shows an error state with an actionable message when the API fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: false,
          database_url_scheme: "sqlite",
        });
      }
      return jsonResponse({ detail: "Database temporarily unavailable" }, 500);
    });

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText("Database temporarily unavailable")
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("create form shows validation messages and keeps entered values on a failed submit", async () => {
    setupApiMock({ engagements: [] });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("No engagements created yet")).toBeInTheDocument();
    });

    const statementInput = screen.getByLabelText(/Initial client statement/i);
    await user.type(statementInput, "Customers report delayed order updates.");
    await user.click(screen.getByRole("button", { name: "Create engagement" }));

    expect(screen.getByText("Engagement name is required.")).toBeInTheDocument();
    expect(screen.getByText("Client name is required.")).toBeInTheDocument();
    expect(statementInput).toHaveValue("Customers report delayed order updates.");
  });

  it("successful create shows a status message and the new row", async () => {
    setupApiMock({ engagements: [] });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("No engagements created yet")).toBeInTheDocument();
    });

    await user.type(
      screen.getByLabelText(/Engagement name/i),
      "Atelier Order Triage"
    );
    await user.type(screen.getByLabelText(/Client name/i), "Atelier Goods");
    await user.type(
      screen.getByLabelText(/Initial client statement/i),
      "Support inbox is overwhelmed after launch."
    );
    await user.click(screen.getByRole("button", { name: "Create engagement" }));

    await waitFor(() => {
      expect(
        screen.getByText('Created engagement "Atelier Order Triage".')
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("cell", { name: /Atelier Order Triage/i })
    ).toBeInTheDocument();
  });

  it("delete requires confirmation and does not delete on cancel", async () => {
    const fetchSpy = setupApiMock({ engagements: [ENGAGEMENT_ONE] });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("cell", {
          name: /Kora Living: Customer support turnaround/i,
        })
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", {
        name: "Delete Kora Living: Customer support turnaround",
      })
    );
    expect(
      screen.getByRole("button", { name: "Confirm delete" })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm delete" })
    ).not.toBeInTheDocument();
    const deleteCalls = fetchSpy.mock.calls.filter(
      ([, init]) => (init?.method ?? "GET").toUpperCase() === "DELETE"
    );
    expect(deleteCalls).toHaveLength(0);
    expect(
      screen.getByRole("cell", {
        name: /Kora Living: Customer support turnaround/i,
      })
    ).toBeInTheDocument();
  });

  it("selecting an engagement makes it active and it survives a reload (localStorage)", async () => {
    setupApiMock({ engagements: [ENGAGEMENT_ONE, ENGAGEMENT_TWO] });
    const user = userEvent.setup();

    const { unmount } = render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("cell", { name: /Northwind: Returns queue review/i })
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Set active" }));

    expect(window.localStorage.getItem(ACTIVE_ENGAGEMENT_STORAGE_KEY)).toBe("2");
    const breadcrumbBefore = screen.getByRole("navigation", {
      name: "Breadcrumb",
    });
    expect(
      within(breadcrumbBefore).getByText("Northwind: Returns queue review")
    ).toBeInTheDocument();

    unmount();

    // Simulate reload with persisted localStorage
    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      const breadcrumbAfter = screen.getByRole("navigation", {
        name: "Breadcrumb",
      });
      expect(
        within(breadcrumbAfter).getByText("Northwind: Returns queue review")
      ).toBeInTheDocument();
    });
  });

  it("deleting the active engagement falls back to another or to none", async () => {
    setupApiMock({ engagements: [ENGAGEMENT_ONE, ENGAGEMENT_TWO] });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("cell", {
          name: /Kora Living: Customer support turnaround/i,
        })
      ).toBeInTheDocument();
    });

    // Delete active engagement #1 -> should fall back to #2
    await user.click(
      screen.getByRole("button", {
        name: "Delete Kora Living: Customer support turnaround",
      })
    );
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => {
      expect(window.localStorage.getItem(ACTIVE_ENGAGEMENT_STORAGE_KEY)).toBe(
        "2"
      );
    });

    // Delete remaining active engagement #2 -> should fall back to none
    await user.click(
      screen.getByRole("button", {
        name: "Delete Northwind: Returns queue review",
      })
    );
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => {
      expect(window.localStorage.getItem(ACTIVE_ENGAGEMENT_STORAGE_KEY)).toBeNull();
      expect(screen.getByText("No engagements created yet")).toBeInTheDocument();
    });
  });

  it("overview shows the engagement summary and the synthetic data notice", async () => {
    setupApiMock({
      engagements: [ENGAGEMENT_ONE],
      brief: null,
      activity: [],
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          level: 3,
          name: "Kora Living: Customer support turnaround",
        })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Kora Living · D2C home-goods retail/i)).toBeInTheDocument();
    expect(screen.getByText("Synthetic demonstration data")).toBeInTheDocument();
  });

  it("overview shows the problem-statement empty state when the brief returns 404", async () => {
    setupApiMock({
      engagements: [ENGAGEMENT_ONE],
      brief: null,
      activity: [],
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText("No problem statement drafted yet")
      ).toBeInTheDocument();
    });
    const discoveryLink = screen.getByRole("link", { name: /Open Discovery/i });
    expect(discoveryLink).toHaveAttribute("href", "/discovery");
  });

  it("overview stage indicator marks the current stage with aria-current", async () => {
    setupApiMock({
      engagements: [ENGAGEMENT_TWO], // stage: diagnose
      brief: null,
      activity: [],
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("list", { name: "Engagement stage progress" })
      ).toBeInTheDocument();
    });

    const stageList = screen.getByRole("list", {
      name: "Engagement stage progress",
    });
    const steps = within(stageList).getAllByRole("listitem");
    expect(steps).toHaveLength(4);
    expect(steps[0]).not.toHaveAttribute("aria-current");
    expect(steps[1]).toHaveAttribute("aria-current", "step");
    expect(within(steps[1]).getByText("Diagnose")).toBeInTheDocument();
    expect(within(steps[1]).getByText("Current stage")).toBeInTheDocument();
  });

  it("overview recent activity renders readable sentences newest first", async () => {
    const entries: AuditLogEntry[] = [
      {
        id: 2,
        engagement_id: 1,
        actor: "Demo operator",
        action: "create",
        entity_type: "note",
        entity_id: "1",
        details: { title: "Operations lead intake interview — Maya Chen" },
        created_at: new Date(Date.now() - 120_000).toISOString(),
      },
      {
        id: 1,
        engagement_id: 1,
        actor: "Demo operator",
        action: "create",
        entity_type: "engagement",
        entity_id: "1",
        details: { name: "Kora Living: Customer support turnaround" },
        created_at: new Date(Date.now() - 600_000).toISOString(),
      },
    ];

    setupApiMock({
      engagements: [ENGAGEMENT_ONE],
      brief: null,
      activity: entries,
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("list", { name: "Recent activity" })
      ).toBeInTheDocument();
    });

    const list = screen.getByRole("list", { name: "Recent activity" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent(
      'Demo operator created interview note "Operations lead intake interview — Maya Chen"'
    );
    expect(rows[1]).toHaveTextContent(
      'Demo operator created engagement "Kora Living: Customer support turnaround"'
    );
  });

  it("overview with no engagements shows the empty state", async () => {
    setupApiMock({ engagements: [] });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("No active engagement loaded")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /Go to Engagements/i });
    expect(link).toHaveAttribute("href", "/engagements");
  });
});
