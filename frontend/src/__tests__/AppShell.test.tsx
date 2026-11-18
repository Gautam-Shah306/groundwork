import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { NAV_ITEMS } from "../lib/navigation";

function mockDefaultApi() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/api/health")) {
      return new Response(
        JSON.stringify({
          status: "ok",
          version: "0.1.0",
          llm_configured: false,
          database_url_scheme: "sqlite",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (url.includes("/api/engagements")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ detail: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("Application shell, navigation, and health status", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockDefaultApi();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sidebar renders all six nav items grouped under Workspace and Stages", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const workspaceGroup = within(nav).getByRole("group", { name: "Workspace" });
    const stagesGroup = within(nav).getByRole("group", { name: "Stages" });

    expect(within(workspaceGroup).getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(within(workspaceGroup).getByRole("link", { name: "Engagements" })).toBeInTheDocument();

    expect(within(stagesGroup).getByRole("link", { name: "Discovery" })).toBeInTheDocument();
    expect(within(stagesGroup).getByRole("link", { name: "Diagnostics" })).toBeInTheDocument();
    expect(within(stagesGroup).getByRole("link", { name: "Prototypes" })).toBeInTheDocument();
    expect(within(stagesGroup).getByRole("link", { name: "Outcomes" })).toBeInTheDocument();
  });

  it("active route's nav item has the active state and aria-current", () => {
    render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const diagnosticsLink = within(nav).getByRole("link", { name: "Diagnostics" });
    const overviewLink = within(nav).getByRole("link", { name: "Overview" });

    expect(diagnosticsLink).toHaveAttribute("aria-current", "page");
    expect(diagnosticsLink.className).toContain("bg-accent-soft");
    expect(diagnosticsLink.className).toContain("text-ink");
    expect(overviewLink).not.toHaveAttribute("aria-current");
  });

  it("each of the six routes renders its title and an EmptyState", async () => {
    for (const item of NAV_ITEMS) {
      const { unmount } = render(
        <MemoryRouter initialEntries={[item.path]}>
          <AppRoutes isDev={false} />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { level: 1, name: item.label })
        ).toBeInTheDocument();
        expect(screen.getByText(item.emptyTitle)).toBeInTheDocument();
      });
      expect(screen.getByText(item.emptyDescription)).toBeInTheDocument();

      unmount();
    }
  });

  it("breadcrumbs reflect the current route", () => {
    render(
      <MemoryRouter initialEntries={["/prototypes"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(breadcrumb).getByText("Groundwork")).toBeInTheDocument();
    expect(within(breadcrumb).getByText("Stages")).toBeInTheDocument();
    expect(within(breadcrumb).getByText("Prototypes")).toHaveAttribute(
      "aria-current",
      "page"
    );
  });

  it("status shows operational when the health call succeeds", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText("System status: operational")
      ).toBeInTheDocument();
    });
  });

  it("status shows unavailable when the health call fails", async () => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/health")) {
        throw new Error("Connection refused");
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText("System status: unavailable")
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Start the backend API or verify the \/api proxy/i)
    ).toBeInTheDocument();
  });

  it("/dev/components is not registered when not in dev mode", () => {
    render(
      <MemoryRouter initialEntries={["/dev/components"]}>
        <AppRoutes isDev={false} />
      </MemoryRouter>
    );

    expect(
      screen.queryByTestId("dev-components-gallery")
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found" })
    ).toBeInTheDocument();
  });
});
