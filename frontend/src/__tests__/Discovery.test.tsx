import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import type {
  BriefSections,
  BriefVersion,
  DiscoveryAnalysis,
  Engagement,
  InterviewNote,
  ProblemBrief,
} from "../lib/api";

const SAMPLE_ENGAGEMENT: Engagement = {
  id: 1,
  name: "Kora Living: Support Turnaround",
  client_name: "Kora Living",
  industry: "D2C home-goods",
  client_statement: "Customers wait 6 hours for initial replies.",
  stage: "discover",
  is_synthetic: true,
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-18T08:00:00Z",
};

const SAMPLE_NOTE: InterviewNote = {
  id: 101,
  engagement_id: 1,
  title: "Head of Support Interview",
  content: "Triage takes 4 hours because tickets are routed manually across three inboxes.",
  created_at: "2026-11-18T09:00:00Z",
  updated_at: "2026-11-18T09:00:00Z",
};

const SAMPLE_SECTIONS: BriefSections = {
  context: "Kora Living support team has 12 agents.",
  themes: [
    {
      id: "th1",
      text: "Manual triage bottleneck",
      source_quote: "tickets are routed manually",
      quote_verified: true,
      origin: "ai",
      status: "ai_draft",
      flags: [],
    },
  ],
  stakeholders: [],
  workflow_steps: [],
  symptoms: [],
  impact: [],
  known_facts: [
    {
      id: "kf1",
      text: "Triage takes 4 hours",
      type: "client_statement",
      source_quote: "Triage takes 4 hours",
      quote_verified: true,
      origin: "ai",
      status: "ai_draft",
      flags: [],
    },
  ],
  hypotheses: [
    {
      id: "h1",
      text: "Shift handoffs might explain triage delays",
      origin: "ai",
      status: "ai_draft",
      flags: [],
    },
  ],
  assumptions: [],
  unknowns: [],
  follow_up_questions: [
    {
      id: "q1",
      question: "What is the agent schedule?",
      status: "open",
    },
  ],
  problem_statement: {
    text: "Support agents experience high volume in email queue, affecting first response time; improvement will be judged by first_response_time",
    status: "ai_draft",
    flags: [],
  },
  candidate_kpis: [
    {
      id: "k1",
      metric_id: "first_response_time",
      rationale: "Direct waiting metric",
      status: "ai_draft",
      flags: [],
    },
  ],
};

const SAMPLE_BRIEF: ProblemBrief = {
  id: 1,
  engagement_id: 1,
  sections: SAMPLE_SECTIONS,
  source: "ai_draft",
  updated_at: "2026-11-18T10:00:00Z",
};

const SAMPLE_ANALYSIS: DiscoveryAnalysis = {
  id: 501,
  engagement_id: 1,
  note_ids: [101],
  status: "completed",
  draft: {
    ...SAMPLE_SECTIONS,
    themes: [
      {
        id: "th_warn",
        text: "Invented queue complaint",
        source_quote: "Not in transcript at all",
        quote_verified: false,
        origin: "ai",
        status: "ai_draft",
        flags: ["quote_not_found"],
      },
    ],
    hypotheses: [
      {
        id: "h_unhedged",
        text: "Triage completely causes the bottleneck",
        origin: "ai",
        status: "ai_draft",
        flags: ["not_hedged"],
      },
    ],
    problem_statement: {
      text: "Agents delay replies because of bad shifts",
      status: "ai_draft",
      flags: ["causal_wording"],
    },
    known_facts: [
      {
        id: "kf_down",
        text: "Backlog is 40%",
        type: "client_statement",
        origin: "ai",
        status: "ai_draft",
        flags: ["type_downgraded"],
      },
    ],
  },
  warnings: [
    {
      code: "quote_not_found",
      section: "themes",
      item_id: "th_warn",
      text: "Invented queue complaint",
      message: "Source quote was not found in notes.",
    },
    {
      code: "not_hedged",
      section: "hypotheses",
      item_id: "h_unhedged",
      text: "Triage completely causes the bottleneck",
      message: "Hypothesis is missing required hedging language.",
    },
    {
      code: "causal_wording",
      section: "problem_statement",
      text: "Agents delay replies because of bad shifts",
      message: "Problem statement contains banned causal language.",
    },
    {
      code: "type_downgraded",
      section: "known_facts",
      item_id: "kf_down",
      text: "Backlog is 40%",
      message: "Observed fact was downgraded to client statement.",
    },
  ],
  error: null,
  model: "openai/gpt-oss-20b",
  usage: { input_tokens: 300, output_tokens: 250, total_tokens: 550 },
  notes_chars: 85,
  created_at: "2026-11-18T10:05:00Z",
  applied_at: null,
};

const SAMPLE_VERSIONS: BriefVersion[] = [
  {
    id: 11,
    engagement_id: 1,
    sections: SAMPLE_SECTIONS,
    source: "ai_draft",
    reason: "apply",
    saved_at: "2026-11-18T10:00:00Z",
  },
  {
    id: 10,
    engagement_id: 1,
    sections: { ...SAMPLE_SECTIONS, context: "Initial draft context" },
    source: "edited",
    reason: "edit",
    saved_at: "2026-11-18T09:30:00Z",
  },
];

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockDiscoveryApi(options: {
  engagements?: Engagement[];
  notes?: InterviewNote[];
  brief?: ProblemBrief | null;
  versions?: BriefVersion[];
  analyses?: DiscoveryAnalysis[];
  llmConfigured?: boolean;
  onAnalyse?: (payload?: unknown) => Promise<Response> | Response;
  onApply?: (aid: number, confirm: boolean) => Promise<Response> | Response;
  onSaveBrief?: (sections: unknown) => Promise<Response> | Response;
  onRestore?: (vid: number) => Promise<Response> | Response;
}) {
  let notes = [...(options.notes ?? [SAMPLE_NOTE])];
  let brief = options.brief !== undefined ? options.brief : SAMPLE_BRIEF;
  let versions = [...(options.versions ?? SAMPLE_VERSIONS)];
  let analyses = [...(options.analyses ?? [])];
  const llmConfigured = options.llmConfigured ?? true;

  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/api/health")) {
      return jsonResponse({
        status: "ok",
        version: "0.1.0",
        llm_configured: llmConfigured,
        database_url_scheme: "sqlite",
      });
    }

    if (url.endsWith("/api/engagements") && method === "GET") {
      return jsonResponse(options.engagements ?? [SAMPLE_ENGAGEMENT]);
    }

    // Notes
    if (url.match(/\/api\/engagements\/\d+\/notes$/) && method === "GET") {
      return jsonResponse(notes);
    }

    if (url.match(/\/api\/engagements\/\d+\/notes$/) && method === "POST") {
      const body = JSON.parse((init?.body as string) || "{}");
      const newNote: InterviewNote = {
        id: Math.floor(Math.random() * 1000) + 200,
        engagement_id: 1,
        title: body.title,
        content: body.content,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      notes.unshift(newNote);
      return jsonResponse(newNote, 201);
    }

    if (url.match(/\/api\/engagements\/\d+\/notes\/\d+$/) && method === "PUT") {
      const body = JSON.parse((init?.body as string) || "{}");
      const match = url.match(/\/api\/engagements\/\d+\/notes\/(\d+)$/);
      const nid = Number(match?.[1]);
      const note = notes.find((n) => n.id === nid);
      if (note) {
        if (body.title) note.title = body.title;
        if (body.content) note.content = body.content;
        return jsonResponse(note);
      }
      return jsonResponse({ detail: "Note not found" }, 404);
    }

    if (url.match(/\/api\/engagements\/\d+\/notes\/\d+$/) && method === "DELETE") {
      const match = url.match(/\/api\/engagements\/\d+\/notes\/(\d+)$/);
      const nid = Number(match?.[1]);
      notes = notes.filter((n) => n.id !== nid);
      return new Response(null, { status: 204 });
    }

    // Brief
    if (url.match(/\/api\/engagements\/\d+\/brief$/) && method === "GET") {
      if (!brief) {
        return jsonResponse({ detail: "Not found" }, 404);
      }
      return jsonResponse(brief);
    }

    if (url.match(/\/api\/engagements\/\d+\/brief$/) && method === "PUT") {
      const body = JSON.parse((init?.body as string) || "{}");
      if (options.onSaveBrief) {
        return options.onSaveBrief(body.sections);
      }
      brief = {
        id: 1,
        engagement_id: 1,
        sections: body.sections,
        source: "edited",
        updated_at: new Date().toISOString(),
      };
      versions.unshift({
        id: versions.length + 1,
        engagement_id: 1,
        sections: body.sections,
        source: "edited",
        reason: "edit",
        saved_at: new Date().toISOString(),
      });
      return jsonResponse(brief);
    }

    // Versions
    if (url.match(/\/api\/engagements\/\d+\/brief\/versions$/) && method === "GET") {
      return jsonResponse(versions);
    }

    if (url.match(/\/api\/engagements\/\d+\/brief\/versions\/\d+\/restore$/) && method === "POST") {
      const match = url.match(/\/api\/engagements\/\d+\/brief\/versions\/(\d+)\/restore$/);
      const vid = Number(match?.[1]);
      if (options.onRestore) {
        return options.onRestore(vid);
      }
      const v = versions.find((ver) => ver.id === vid);
      if (v) {
        brief = {
          id: 1,
          engagement_id: 1,
          sections: v.sections,
          source: v.source as "ai_draft" | "edited",
          updated_at: new Date().toISOString(),
        };
        versions.unshift({
          id: versions.length + 1,
          engagement_id: 1,
          sections: v.sections,
          source: v.source,
          reason: "restore",
          saved_at: new Date().toISOString(),
        });
        return jsonResponse(brief);
      }
      return jsonResponse({ detail: "Version not found" }, 404);
    }

    // Discovery analyses
    if (url.match(/\/api\/engagements\/\d+\/discovery\/analyses$/) && method === "GET") {
      return jsonResponse(analyses);
    }

    if (url.match(/\/api\/engagements\/\d+\/discovery\/analyse$/) && method === "POST") {
      if (options.onAnalyse) {
        return options.onAnalyse(JSON.parse((init?.body as string) || "{}"));
      }
      analyses.unshift(SAMPLE_ANALYSIS);
      return jsonResponse(SAMPLE_ANALYSIS);
    }

    if (url.match(/\/api\/engagements\/\d+\/discovery\/analyses\/\d+\/apply$/) && method === "POST") {
      const match = url.match(/\/api\/engagements\/\d+\/discovery\/analyses\/(\d+)\/apply$/);
      const aid = Number(match?.[1]);
      const body = JSON.parse((init?.body as string) || "{}");
      if (options.onApply) {
        return options.onApply(aid, body.confirm_replace);
      }
      brief = {
        id: 1,
        engagement_id: 1,
        sections: SAMPLE_ANALYSIS.draft!,
        source: "ai_draft",
        updated_at: new Date().toISOString(),
      };
      return jsonResponse(brief);
    }

    return jsonResponse({ detail: "Endpoint unhandled in mock" }, 404);
  });
}

function renderDiscovery() {
  return render(
    <MemoryRouter initialEntries={["/discovery"]}>
      <AppRoutes />
    </MemoryRouter>
  );
}

describe("Discovery Workspace (Prompt 7 Scenarios)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. renders empty state when no active engagement
  it("1. renders empty state when no active engagement", async () => {
    mockDiscoveryApi({ engagements: [] });
    renderDiscovery();

    expect(await screen.findByText("No engagement selected")).toBeInTheDocument();
  });

  // 2. renders notes list and brief when engagement selected
  it("2. renders notes list and brief when engagement selected", async () => {
    mockDiscoveryApi({});
    renderDiscovery();

    expect(await screen.findByText("Head of Support Interview")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Kora Living support team has 12 agents.")).toBeInTheDocument();
  });

  // 3. note word count computed correctly
  it("3. note word count computed correctly", async () => {
    mockDiscoveryApi({});
    renderDiscovery();

    // "Triage takes 4 hours because tickets are routed manually across three inboxes." has 12 words
    expect(await screen.findByText(/12 words/)).toBeInTheDocument();
  });

  // 4. add note form creates note and updates list
  it("4. add note form creates note and updates list", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("Head of Support Interview");
    const addBtn = screen.getByRole("button", { name: /Add note/i });
    await user.click(addBtn);

    const titleInput = screen.getByPlaceholderText(/Interview title/i);
    const contentInput = screen.getByPlaceholderText(/Paste verbatim interview notes/i);
    await user.type(titleInput, "Team Lead Interview");
    await user.type(contentInput, "Agents are overwhelmed during peak shifts.");

    const saveBtn = screen.getByRole("button", { name: /Save note/i });
    await user.click(saveBtn);

    expect(await screen.findByText("Team Lead Interview")).toBeInTheDocument();
  });

  // 5. edit note updates note content
  it("5. edit note updates note content", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("Head of Support Interview");
    const editBtn = screen.getByTitle("Edit note");
    await user.click(editBtn);

    const contentEdit = screen.getByRole("textbox", { name: "Edit note content" });
    await user.clear(contentEdit);
    await user.type(contentEdit, "Updated note content verbatim.");

    const saveBtn = screen.getByRole("button", { name: "Save" });
    await user.click(saveBtn);

    expect(await screen.findByText("Updated note content verbatim.")).toBeInTheDocument();
  });

  // 6. delete note prompts for confirmation and removes from list
  it("6. delete note prompts for confirmation and removes from list", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("Head of Support Interview");
    const deleteBtn = screen.getByTitle("Delete note");
    await user.click(deleteBtn);

    expect(await screen.findByText("Delete this note?")).toBeInTheDocument();
    const confirmBtn = screen.getByRole("button", { name: "Delete" });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByText("Head of Support Interview")).not.toBeInTheDocument();
    });
  });

  // 7. select all / deselect all toggles all checkboxes
  it("7. select all / deselect all toggles all checkboxes", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("1 of 1 selected");
    const deselectBtn = screen.getByRole("button", { name: "Deselect all" });
    await user.click(deselectBtn);

    expect(await screen.findByText("0 of 1 selected")).toBeInTheDocument();
    const selectBtn = screen.getByRole("button", { name: "Select all" });
    await user.click(selectBtn);

    expect(await screen.findByText("1 of 1 selected")).toBeInTheDocument();
  });

  // 8. character count updates as notes are selected
  it("8. character count updates as notes are selected", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("1 of 1 selected");
    const charDisplayBefore = screen.getByText(new RegExp(`${SAMPLE_NOTE.title.length + SAMPLE_NOTE.content.length} / 30,000 chars`));
    expect(charDisplayBefore).toBeInTheDocument();

    const deselectBtn = screen.getByRole("button", { name: "Deselect all" });
    await user.click(deselectBtn);

    expect(await screen.findByText("0 / 30,000 chars")).toBeInTheDocument();
  });

  // 9. analyse button disabled when no notes selected
  it("9. analyse button disabled when no notes selected", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({});
    renderDiscovery();

    await screen.findByText("1 of 1 selected");
    const deselectBtn = screen.getByRole("button", { name: "Deselect all" });
    await user.click(deselectBtn);

    const analyseBtn = screen.getByRole("button", { name: /Analyse/i });
    expect(analyseBtn).toBeDisabled();
  });

  // 10. analyse button disabled when notes exceed 30,000 chars with banner
  it("10. analyse button disabled when notes exceed 30,000 chars with banner", async () => {
    const oversizeNote: InterviewNote = {
      id: 102,
      engagement_id: 1,
      title: "Huge Note",
      content: "x".repeat(30005),
      created_at: "2026-11-18T09:00:00Z",
      updated_at: "2026-11-18T09:00:00Z",
    };
    mockDiscoveryApi({ notes: [oversizeNote] });
    renderDiscovery();

    expect(await screen.findByText(/Selected notes exceed the 30,000 character limit/i)).toBeInTheDocument();
    const analyseBtn = screen.getByRole("button", { name: /Analyse/i });
    expect(analyseBtn).toBeDisabled();
  });

  // 11. analyse button disabled and helper text shown when llm_configured is false
  it("11. analyse button disabled and helper text shown when llm_configured is false", async () => {
    mockDiscoveryApi({ llmConfigured: false });
    renderDiscovery();

    expect(await screen.findByText(/Configure LLM_API_KEY in .env/i)).toBeInTheDocument();
    const analyseBtn = screen.getByRole("button", { name: /Analyse/i });
    expect(analyseBtn).toBeDisabled();
  });

  // 12. analyse triggers POST /discovery/analyse and renders draft in review mode
  it("12. analyse triggers POST /discovery/analyse and renders draft in review mode", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({ analyses: [] });
    renderDiscovery();

    await screen.findByText("Head of Support Interview");
    const analyseBtn = screen.getByRole("button", { name: /Analyse 1 selected note/i });
    await user.click(analyseBtn);

    expect(await screen.findByText("AI Analysis Review")).toBeInTheDocument();
    expect(await screen.findByText("Proposed Problem Brief")).toBeInTheDocument();
  });

  // 13. draft displays AI-generated draft disclosure
  it("13. draft displays AI-generated draft disclosure", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText("AI-generated draft")).toBeInTheDocument();
    expect(await screen.findByText("AI recommendation")).toBeInTheDocument();
  });

  // 14. items with source_quote show verbatim quote
  it("14. items with source_quote show verbatim quote", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText(/“Not in transcript at all”/)).toBeInTheDocument();
  });

  // 15. items with quote_not_found show 'Quote not found in notes' pill
  it("15. items with quote_not_found show 'Quote not found in notes' pill", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText("Quote not found in notes")).toBeInTheDocument();
  });

  // 16. hypotheses with not_hedged show 'Not hedged' pill
  it("16. hypotheses with not_hedged show 'Not hedged' pill", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText("Not hedged")).toBeInTheDocument();
  });

  // 17. problem statement with causal_wording shows 'Wording implies a cause' pill
  it("17. problem statement with causal_wording shows 'Wording implies a cause' pill", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText("Wording implies a cause")).toBeInTheDocument();
  });

  // 18. known_fact with type_downgraded shows downgrade pill
  it("18. known_fact with type_downgraded shows downgrade pill", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText("Observed fact downgraded to client statement")).toBeInTheDocument();
  });

  // 19. warnings summary banner rendered when analysis has warnings
  it("19. warnings summary banner rendered when analysis has warnings", async () => {
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    expect(await screen.findByText(/4 review flags detected/i)).toBeInTheDocument();
  });

  // 20. apply button sends POST /apply and exits review mode to editor
  it("20. apply button sends POST /apply and exits review mode to editor", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS], brief: { ...SAMPLE_BRIEF, source: "ai_draft" } });
    renderDiscovery();

    const applyBtn = await screen.findByRole("button", { name: /Apply to Brief/i });
    await user.click(applyBtn);

    // Review mode should close and brief editor shows up
    expect(await screen.findByText("Editable Document")).toBeInTheDocument();
  });

  // 21. apply on edited brief shows overwrite confirmation modal
  it("21. apply on edited brief shows overwrite confirmation modal", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({
      analyses: [SAMPLE_ANALYSIS],
      brief: { ...SAMPLE_BRIEF, source: "edited" },
    });
    renderDiscovery();

    const applyBtn = await screen.findByRole("button", { name: /Apply to Brief/i });
    await user.click(applyBtn);

    expect(await screen.findByText("Overwrite existing brief edits?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm & overwrite" })).toBeInTheDocument();
  });

  // 22. discard button exits review mode without applying
  it("22. discard button exits review mode without applying", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({ analyses: [SAMPLE_ANALYSIS] });
    renderDiscovery();

    const discardBtn = await screen.findByRole("button", { name: /Discard draft/i });
    await user.click(discardBtn);

    expect(await screen.findByText("Editable Document")).toBeInTheDocument();
  });

  // 23. brief editor dirty state enables save button and triggers beforeunload guard
  it("23. brief editor dirty state enables save button and triggers beforeunload guard", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({ analyses: [] });
    renderDiscovery();

    await screen.findByText("Editable Document");
    const saveBtn = screen.getByRole("button", { name: /Save changes/i });
    expect(saveBtn).toBeDisabled();

    // Type in context
    const contextArea = screen.getByPlaceholderText(/Summarize client background/i);
    await user.type(contextArea, " Added fresh details.");

    expect(saveBtn).not.toBeDisabled();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  // 24. version history lists versions with timestamp and reason
  it("24. version history lists versions with timestamp and reason", async () => {
    mockDiscoveryApi({ analyses: [] });
    renderDiscovery();

    expect(await screen.findByText("Applied from AI draft")).toBeInTheDocument();
    expect(await screen.findByText("Manual edit")).toBeInTheDocument();
  });

  // 25. restore version sends POST /restore and updates editor
  it("25. restore version sends POST /restore and updates editor", async () => {
    const user = userEvent.setup();
    mockDiscoveryApi({ analyses: [] });
    renderDiscovery();

    const restoreBtn = await screen.findByRole("button", { name: /Restore/i });
    await user.click(restoreBtn);

    expect(await screen.findByText("Restore this version?")).toBeInTheDocument();
    const confirmBtn = screen.getByRole("button", { name: "Confirm" });
    await user.click(confirmBtn);

    expect(await screen.findByDisplayValue("Initial draft context")).toBeInTheDocument();
  });
});
