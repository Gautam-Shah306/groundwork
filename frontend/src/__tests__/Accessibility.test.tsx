import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { ACTIVE_ENGAGEMENT_STORAGE_KEY } from "../context/EngagementContext";
import type { Engagement } from "../lib/api";

const MOCK_ENGAGEMENT: Engagement = {
  id: 1,
  name: "Kora Living",
  client_name: "Kora Living",
  industry: "D2C home-goods retail",
  client_statement:
    "Our customer support team is overwhelmed. Customers are waiting too long for responses.",
  stage: "build",
  is_synthetic: true,
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-18T08:00:00Z",
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// color-contrast is disabled because jsdom cannot compute it
const AXE_OPTIONS: axe.RunOptions = {
  rules: {
    "color-contrast": { enabled: false },
  },
};

describe("Accessibility compliance with axe-core across 6 routes (C2)", () => {
  beforeEach(() => {
    window.localStorage.setItem(
      ACTIVE_ENGAGEMENT_STORAGE_KEY,
      JSON.stringify(MOCK_ENGAGEMENT)
    );

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes("/api/health")) {
        return jsonResponse({
          status: "ok",
          version: "0.1.0",
          llm_configured: true,
          database_url_scheme: "sqlite",
        });
      }
      if (url.includes("/api/engagements/1/outcomes/kpi-catalogue")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/outcomes/kpis")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/outcomes/interventions")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/outcomes/simulations")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/outcomes/review")) {
        return jsonResponse({ detail: "Not found" }, 404);
      }
      if (url.includes("/api/engagements/1/evaluation/runs")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/triage/proposals")) {
        return jsonResponse({ proposals: [], total: 0 });
      }
      if (url.includes("/api/engagements/1/triage/config")) {
        return jsonResponse({
          queues: [
            { id: "urgent_tier_2", name: "Urgent Tier 2", priority: "urgent" },
            { id: "standard_tier_1", name: "Standard Tier 1", priority: "standard" },
          ],
          categories: ["order_tracking", "damaged_item"],
          signals: { damaged_package: { description: "Damaged packaging" } },
          rules: [],
        });
      }
      if (url.includes("/api/engagements/1/activity")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/brief/versions")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/brief")) {
        return jsonResponse({
          id: 1,
          engagement_id: 1,
          sections: {
            context: "Test context",
            themes: [],
            stakeholders: [],
            workflow_steps: [],
            symptoms: [],
            impact: [],
            known_facts: [],
            hypotheses: [],
            assumptions: [],
            unknowns: [],
            follow_up_questions: [],
            problem_statement: { text: "Test problem", status: "ai_draft", flags: [] },
            candidate_kpis: [],
          },
          source: "ai_draft",
          updated_at: new Date().toISOString(),
        });
      }
      if (url.includes("/api/engagements/1/discovery/analyses")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/notes")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1/datasets")) {
        return jsonResponse([]);
      }
      if (url.includes("/api/engagements/1")) {
        return jsonResponse(MOCK_ENGAGEMENT);
      }
      if (url.includes("/api/engagements")) {
        return jsonResponse([MOCK_ENGAGEMENT]);
      }
      return jsonResponse({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("test_route_has_no_serious_axe_violations for Overview", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Engagements", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/engagements"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Discovery", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/discovery"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Diagnostics", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/diagnostics"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Prototypes (Triage workspace)", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/prototypes"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Prototypes (Agent evaluation)", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/prototypes"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const evalTab = await screen.findByRole("tab", { name: /Agent evaluation/i });
    fireEvent.click(evalTab);

    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });

  it("test_route_has_no_serious_axe_violations for Outcomes", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/outcomes"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    await screen.findByRole("main");
    const results = await axe.run(container, AXE_OPTIONS);
    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCritical).toEqual([]);
  });
});
