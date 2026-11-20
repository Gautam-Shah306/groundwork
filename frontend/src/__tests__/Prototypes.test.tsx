import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EngagementProvider } from "../context/EngagementContext";
import {
  SubmitTicketForm,
  ProposalInbox,
  ProposalDetail,
  PipelineTrace,
  ReplyEditor,
  DecisionControls,
  ActionHistory,
  SignalList,
} from "../components/prototypes";
import { PrototypesPage } from "../pages/PrototypesPage";
import type {
  AuditLogEntry,
  TriageProposalResponse,
} from "../lib/api";

const MOCK_PROPOSAL: TriageProposalResponse = {
  id: 10,
  engagement_id: 1,
  ticket_hash: "hash123",
  subject: "Broken lamp upon delivery",
  body: "My order KL-5544 lamp arrived broken into pieces. <script>alert('xss')</script>",
  channel: "chat",
  category: "damaged_item",
  secondary_category: null,
  priority: "high",
  queue: "Returns and refunds",
  escalation: false,
  rule_id: "R-DAMAGE",
  rule_definition: "Damaged, defective, or wrong delivered items require High priority.",
  signals: [
    {
      signal: "item_damaged_or_defective",
      source_quote: "lamp arrived broken into pieces",
      quote_verified: true,
    },
    {
      signal: "explicit_urgency",
      source_quote: "need it urgently today",
      quote_verified: false,
    },
  ],
  rationale: "Customer reports shattered merchandise upon arrival.",
  draft_reply: "I am sorry your lamp arrived broken. Please provide photos of [ORDER_ID].",
  policy_refs: ["2. Replacements for Damaged or Wrong Items"],
  reviewer_note: "Check outer carton photo for transit damage claim.",
  flags: [
    {
      code: "signal_quote_not_found",
      message: "Quote for signal explicit_urgency not found verbatim.",
      where: "signals",
    },
  ],
  tool_trace: [
    {
      call_id: "c1",
      tool: "classify_ticket",
      args: { body_chars: 82, channel: "chat" },
      ok: true,
      duration_ms: 120,
    },
    {
      call_id: "c2",
      tool: "recommend_priority",
      args: { signals_count: 2, category: "damaged_item" },
      ok: true,
      duration_ms: 1,
    },
    {
      call_id: "c3",
      tool: "draft_ticket_response",
      args: { category: "damaged_item", priority: "high" },
      ok: true,
      duration_ms: 150,
    },
    {
      call_id: "c4",
      tool: "create_triage_proposal",
      args: { flags_count: 1 },
      ok: true,
      duration_ms: 5,
    },
  ],
  model: "fake-test-model",
  status: "awaiting_approval",
  final_values: null,
  decided_by: null,
  decision_reason: null,
  edited: false,
  created_at: "2026-11-19T10:00:00Z",
  decided_at: null,
};

const MOCK_HISTORY: AuditLogEntry[] = [
  {
    id: 1,
    engagement_id: 1,
    actor: "triage_pipeline",
    action: "triage.proposal_created",
    entity_type: "triage_proposal",
    entity_id: "10",
    details: {
      proposed_category: "damaged_item",
      proposed_priority: "high",
      proposed_queue: "Returns and refunds",
    },
    created_at: "2026-11-19T10:00:05Z",
  },
];

describe("Support Triage Prototype Frontend Components", () => {
  // 1. SubmitTicketForm renders inputs and character counter
  it("1. SubmitTicketForm renders subject, body, channel, and character counter", () => {
    render(
      <SubmitTicketForm
        engagementId={1}
        llmConfigured={true}
        onProposalCreated={vi.fn()}
      />
    );

    expect(screen.getByLabelText(/Subject/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Ticket Body/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Channel/i)).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 4000/i)).toBeInTheDocument();
  });

  // 2. SubmitTicketForm disclosure line
  it("2. SubmitTicketForm shows provider disclosure line", () => {
    render(
      <SubmitTicketForm
        engagementId={1}
        llmConfigured={true}
        onProposalCreated={vi.fn()}
      />
    );

    expect(
      screen.getByText(/The ticket text is sent to the configured AI provider/i)
    ).toBeInTheDocument();
  });

  // 3. SubmitTicketForm disabled when llmConfigured is false
  it("3. SubmitTicketForm disables inputs and shows banner when llmConfigured is false", () => {
    render(
      <SubmitTicketForm
        engagementId={1}
        llmConfigured={false}
        onProposalCreated={vi.fn()}
      />
    );

    expect(screen.getByText(/Assistant not configured/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Ticket Body/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /Generate Proposal/i })).toBeDisabled();
  });

  // 4. SubmitTicketForm load example ticket
  it("4. SubmitTicketForm loads example ticket on button click", async () => {
    const user = userEvent.setup();
    render(
      <SubmitTicketForm
        engagementId={1}
        llmConfigured={true}
        onProposalCreated={vi.fn()}
      />
    );

    const damagedBtn = screen.getByRole("button", { name: /Damaged/i });
    await user.click(damagedBtn);

    const bodyInput = screen.getByLabelText(/Ticket Body/i) as HTMLTextAreaElement;
    expect(bodyInput.value).toContain("lamp arrived broken");
  });

  // 5. SubmitTicketForm duplicate notice
  it("5. SubmitTicketForm shows duplicate notice when duplicate proposal returned", async () => {
    const user = userEvent.setup();
    const mockOnCreated = vi.fn();

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({ proposal: MOCK_PROPOSAL, duplicate: true }),
    } as Response);

    render(
      <SubmitTicketForm
        engagementId={1}
        llmConfigured={true}
        onProposalCreated={mockOnCreated}
      />
    );

    await user.type(screen.getByLabelText(/Ticket Body/i), "My order KL-5544 lamp is broken.");
    await user.click(screen.getByRole("button", { name: /Generate Proposal/i }));

    await waitFor(() => {
      expect(screen.getByText(/This ticket already has an existing proposal/i)).toBeInTheDocument();
      expect(mockOnCreated).toHaveBeenCalledWith(MOCK_PROPOSAL, true);
    });
    vi.restoreAllMocks();
  });

  // 6. ProposalInbox renders table columns
  it("6. ProposalInbox renders proposal table with subject, category, priority, queue, status", () => {
    render(
      <ProposalInbox
        proposals={[MOCK_PROPOSAL]}
        selectedProposalId={10}
        onSelectProposal={vi.fn()}
        statusFilter="all"
        onStatusFilterChange={vi.fn()}
      />
    );

    expect(screen.getByText("Broken lamp upon delivery")).toBeInTheDocument();
    expect(screen.getByText("damaged_item")).toBeInTheDocument();
    expect(screen.getByText("Returns and refunds")).toBeInTheDocument();
  });

  // 7. ProposalInbox renders StatusPills for priority and status
  it("7. ProposalInbox renders priority and status StatusPills with text", () => {
    render(
      <ProposalInbox
        proposals={[MOCK_PROPOSAL]}
        selectedProposalId={null}
        onSelectProposal={vi.fn()}
        statusFilter="all"
        onStatusFilterChange={vi.fn()}
      />
    );

    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getAllByText("Awaiting approval").length).toBeGreaterThanOrEqual(1);
  });

  // 8. ProposalInbox status filter buttons
  it("8. ProposalInbox switches status filter on tab click", async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    render(
      <ProposalInbox
        proposals={[MOCK_PROPOSAL]}
        selectedProposalId={null}
        onSelectProposal={vi.fn()}
        statusFilter="all"
        onStatusFilterChange={onFilterChange}
      />
    );

    await user.click(screen.getByRole("button", { name: "Approved" }));
    expect(onFilterChange).toHaveBeenCalledWith("approved");
  });

  // 9. ProposalInbox empty state
  it("9. ProposalInbox renders empty state when proposals array is empty", () => {
    render(
      <ProposalInbox
        proposals={[]}
        selectedProposalId={null}
        onSelectProposal={vi.fn()}
        statusFilter="all"
        onStatusFilterChange={vi.fn()}
      />
    );

    expect(screen.getByText(/No proposals found/i)).toBeInTheDocument();
  });

  // 10. ProposalInbox selection callback
  it("10. ProposalInbox calls onSelectProposal when row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ProposalInbox
        proposals={[MOCK_PROPOSAL]}
        selectedProposalId={null}
        onSelectProposal={onSelect}
        statusFilter="all"
        onStatusFilterChange={vi.fn()}
      />
    );

    await user.click(screen.getByText("Broken lamp upon delivery"));
    expect(onSelect).toHaveBeenCalledWith(10);
  });

  // 11. ProposalDetail ticket text rendered strictly as plain text (escapes HTML/tags)
  it("11. ProposalDetail renders ticket text as plain text without executing HTML", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(
      screen.getByText(/<script>alert\('xss'\)<\/script>/i)
    ).toBeInTheDocument();
  });

  // 12. ProposalDetail AI recommendation section with TypeLabel
  it("12. ProposalDetail renders AI recommendation section with TypeLabel", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(screen.getByText("AI recommendation")).toBeInTheDocument();
    expect(screen.getByText("Proposed Triage Assessment")).toBeInTheDocument();
  });

  // 13. ProposalDetail shows Deterministic rule label and definition
  it("13. ProposalDetail shows Deterministic rule label, rule ID, and plain-language definition", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(screen.getByText(/Deterministic rule:/i)).toBeInTheDocument();
    expect(screen.getByText("R-DAMAGE")).toBeInTheDocument();
    expect(
      screen.getByText("Damaged, defective, or wrong delivered items require High priority.")
    ).toBeInTheDocument();
  });

  // 14. SignalList renders verified and unverified badges
  it("14. SignalList displays verbatim quotes and verified / quote-not-found markers", () => {
    render(<SignalList signals={MOCK_PROPOSAL.signals} />);

    expect(screen.getByText("item_damaged_or_defective")).toBeInTheDocument();
    expect(screen.getByText("Verified quote")).toBeInTheDocument();
    expect(screen.getByText("Quote not found in ticket text")).toBeInTheDocument();
    expect(screen.getByText(/“lamp arrived broken into pieces”/i)).toBeInTheDocument();
  });

  // 15. ProposalDetail AI rationale with Hypothesis TypeLabel
  it("15. ProposalDetail renders AI rationale with Hypothesis TypeLabel", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(screen.getByText("Hypothesis")).toBeInTheDocument();
    expect(
      screen.getByText("Customer reports shattered merchandise upon arrival.")
    ).toBeInTheDocument();
  });

  // 16. ProposalDetail review flags displayed
  it("16. ProposalDetail renders review flags with code and message", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(screen.getByText("signal_quote_not_found")).toBeInTheDocument();
    expect(
      screen.getByText("Quote for signal explicit_urgency not found verbatim.")
    ).toBeInTheDocument();
  });

  // 17. ProposalDetail policy references
  it("17. ProposalDetail lists cited policy references", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(
      screen.getByText("2. Replacements for Damaged or Wrong Items")
    ).toBeInTheDocument();
  });

  // 18. ProposalDetail reviewer note labeled AI note
  it("18. ProposalDetail renders AI note for human reviewer", () => {
    render(
      <ProposalDetail
        proposal={MOCK_PROPOSAL}
        onProposalUpdated={vi.fn()}
        history={MOCK_HISTORY}
      />
    );

    expect(screen.getByText(/AI Note for Human Reviewer/i)).toBeInTheDocument();
    expect(
      screen.getByText("Check outer carton photo for transit damage claim.")
    ).toBeInTheDocument();
  });

  // 19. PipelineTrace renders 4 steps with status and duration
  it("19. PipelineTrace renders 4 steps with duration and status badges", () => {
    render(<PipelineTrace steps={MOCK_PROPOSAL.tool_trace} />);

    expect(screen.getByText("classify_ticket")).toBeInTheDocument();
    expect(screen.getByText("recommend_priority")).toBeInTheDocument();
    expect(screen.getByText("draft_ticket_response")).toBeInTheDocument();
    expect(screen.getByText("create_triage_proposal")).toBeInTheDocument();
    expect(screen.getByText("120ms")).toBeInTheDocument();
    expect(screen.getAllByText("Success")).toHaveLength(4);
  });

  // 20. PipelineTrace arguments summary does not expose ticket text
  it("20. PipelineTrace argument summaries do NOT contain ticket body text", async () => {
    const user = userEvent.setup();
    render(<PipelineTrace steps={MOCK_PROPOSAL.tool_trace} />);

    const stepBtn = screen.getByRole("button", { name: /classify_ticket/i });
    await user.click(stepBtn);

    expect(screen.getByText(/Arguments Summary/i)).toBeInTheDocument();
    expect(screen.queryByText("lamp arrived broken into pieces")).not.toBeInTheDocument();
  });

  // 21. ReplyEditor renders textarea with char count and flags placeholders
  it("21. ReplyEditor flags unresolved placeholders with warning banner", () => {
    render(
      <ReplyEditor
        reply="Please provide your [ORDER_ID] and [CUSTOMER_NAME]."
        readOnly={false}
      />
    );

    expect(screen.getByText(/2 unresolved placeholders detected/i)).toBeInTheDocument();
    expect(screen.getByText("[ORDER_ID]")).toBeInTheDocument();
    expect(screen.getByText("[CUSTOMER_NAME]")).toBeInTheDocument();
  });

  // 22. DecisionControls renders Approve, Edit, Reject buttons when awaiting approval
  it("22. DecisionControls renders Approve, Edit, and Reject buttons", () => {
    render(
      <DecisionControls
        proposal={MOCK_PROPOSAL}
        onDecisionRecorded={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: /Approve proposal/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Edit proposal/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeInTheDocument();
  });

  // 23. DecisionControls confirmation modal states nothing sent to customers
  it("23. DecisionControls confirmation step explicitly notes nothing sent to customers", async () => {
    const user = userEvent.setup();
    render(
      <DecisionControls
        proposal={MOCK_PROPOSAL}
        onDecisionRecorded={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: /Approve proposal/i }));

    expect(
      screen.getByText(/Confirm Human Approval Decision/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/nothing is sent to customers/i)
    ).toBeInTheDocument();
  });

  // 24. DecisionControls shows read-only summary when already decided
  it("24. DecisionControls renders summary banner when proposal is already approved", () => {
    const approvedProposal: TriageProposalResponse = {
      ...MOCK_PROPOSAL,
      status: "approved",
      decided_by: "Lead Operator",
      decided_at: "2026-11-19T11:00:00Z",
    };

    render(
      <DecisionControls
        proposal={approvedProposal}
        onDecisionRecorded={vi.fn()}
      />
    );

    expect(screen.getByText(/Proposal Approved/i)).toBeInTheDocument();
    expect(screen.getByText(/Decided by Lead Operator/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve proposal/i })).not.toBeInTheDocument();
  });

  // 25. ActionHistory renders chronological audit events
  it("25. ActionHistory renders chronological events with actor and action", () => {
    render(<ActionHistory history={MOCK_HISTORY} />);

    expect(screen.getByText("triage.proposal_created")).toBeInTheDocument();
    expect(screen.getByText(/by triage_pipeline/i)).toBeInTheDocument();
    expect(screen.getByText(/Proposed:/i)).toBeInTheDocument();
  });

  // 26. PrototypesPage renders persistent notice and SyntheticDataNotice
  it("26. PrototypesPage renders persistent notice that nothing is sent to customers", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/health")) {
        return {
          ok: true,
          json: async () => ({ status: "ok", llm_configured: true }),
        } as Response;
      }
      if (u.includes("/history")) {
        return {
          ok: true,
          json: async () => MOCK_HISTORY,
        } as Response;
      }
      if (u.includes("/api/engagements/1/triage/proposals/10")) {
        return {
          ok: true,
          json: async () => MOCK_PROPOSAL,
        } as Response;
      }
      if (u.includes("/api/engagements/1/triage/proposals")) {
        return {
          ok: true,
          json: async () => ({ items: [MOCK_PROPOSAL], total: 1, page: 1, page_size: 50 }),
        } as Response;
      }
      if (u.includes("/api/engagements")) {
        return {
          ok: true,
          json: async () => [
            {
              id: 1,
              name: "Kora Living",
              client_name: "Kora Living",
              stage: "build",
              is_synthetic: true,
              created_at: "2026-11-19T08:00:00Z",
              updated_at: "2026-11-19T08:00:00Z",
            },
          ],
        } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });

    window.localStorage.setItem("groundwork.activeEngagementId", "1");

    render(
      <MemoryRouter>
        <EngagementProvider>
          <PrototypesPage />
        </EngagementProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Proposed actions only. Nothing is sent to customers./i)
      ).toBeInTheDocument();
      expect(
        screen.getAllByText(/Synthetic demonstration data/i).length
      ).toBeGreaterThanOrEqual(1);
    });

    vi.restoreAllMocks();
  });

  // 27. test_draft_unavailable_proposal_allows_manual_reply_and_blocks_empty_approval
  it("test_draft_unavailable_proposal_allows_manual_reply_and_blocks_empty_approval", async () => {
    const draftUnavailableProposal: TriageProposalResponse = {
      ...MOCK_PROPOSAL,
      id: 99,
      draft_reply: "",
      flags: [
        {
          code: "draft_unavailable",
          message: "The draft reply could not be generated.",
          where: "draft_reply",
        },
      ],
      status: "awaiting_approval",
    };

    render(
      <ProposalDetail
        proposal={draftUnavailableProposal}
        onProposalUpdated={vi.fn()}
        history={[]}
      />
    );

    // Displays the plain-language message
    expect(
      screen.getAllByText(/The draft reply could not be generated. Write a reply to approve this proposal./i).length
    ).toBeGreaterThanOrEqual(1);

    // Approve button is disabled because reply is empty
    const approveBtn = screen.getByRole("button", { name: /Approve proposal/i });
    expect(approveBtn).toBeDisabled();

    // The reply editor textarea is available and empty
    const textarea = screen.getByPlaceholderText(/Enter or edit customer reply draft.../i);
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveValue("");

    // Typing a manual reply enables approval
    await userEvent.type(textarea, "Manual operator reply for customer.");
    expect(approveBtn).not.toBeDisabled();
  });

  // 28. test_unresolved_placeholder_detection_uses_the_closed_list
  it("test_unresolved_placeholder_detection_uses_the_closed_list", () => {
    render(
      <ReplyEditor
        reply="Your refund of [REFUND_AMOUNT] has been processed. Reference [UNKNOWN_TOKEN] for details."
      />
    );

    // [REFUND_AMOUNT] from closed list is recognized as unresolved placeholder
    expect(screen.getByText("[REFUND_AMOUNT]")).toBeInTheDocument();
    expect(screen.getByText(/1 unresolved placeholder detected:/i)).toBeInTheDocument();

    // [UNKNOWN_TOKEN] is reported as unknown
    expect(screen.getByText("[UNKNOWN_TOKEN] (unknown)")).toBeInTheDocument();
    expect(screen.getByText(/1 unknown placeholder detected:/i)).toBeInTheDocument();
  });
});
