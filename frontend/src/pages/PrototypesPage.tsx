import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FlaskConical, ShieldAlert, Sparkles } from "lucide-react";
import { useEngagement } from "../context/EngagementContext";
import {
  EmptyState,
  Eyebrow,
  SyntheticDataNotice,
} from "../components/ui";
import {
  SubmitTicketForm,
  ProposalInbox,
  ProposalDetail,
} from "../components/prototypes";
import { EvaluationTab } from "../components/evaluation";
import {
  fetchHealth,
  fetchProposalHistory,
  fetchTriageProposal,
  fetchTriageProposals,
  type AuditLogEntry,
  type TriageProposalResponse,
} from "../lib/api";

export function PrototypesPage() {
  const { activeEngagement } = useEngagement();
  const engagementId = activeEngagement?.id;

  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") === "evaluation" ? "evaluation" : "triage";

  const [llmConfigured, setLlmConfigured] = useState(true);
  const [proposals, setProposals] = useState<TriageProposalResponse[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<number | null>(null);
  const [selectedProposal, setSelectedProposal] = useState<TriageProposalResponse | null>(null);
  const [proposalHistory, setProposalHistory] = useState<AuditLogEntry[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [isLoadingProposals, setIsLoadingProposals] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const handleTabChange = (tab: "triage" | "evaluation") => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", tab);
      return next;
    });
  };

  // Check LLM config on mount
  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((h) => {
        if (!cancelled) setLlmConfigured(h.llm_configured);
      })
      .catch(() => {
        if (!cancelled) setLlmConfigured(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch proposals when engagementId or statusFilter changes
  const loadProposals = useCallback(async () => {
    if (!engagementId) return;
    setIsLoadingProposals(true);
    try {
      const res = await fetchTriageProposals(engagementId, {
        status: statusFilter === "all" ? undefined : statusFilter,
        page: 1,
        pageSize: 50,
      });
      setProposals(res.items || []);

      // Auto-select first proposal if none selected
      if (res.items && res.items.length > 0 && !selectedProposalId) {
        setSelectedProposalId(res.items[0].id);
      }
    } catch {
      // Failed to load proposals
    } finally {
      setIsLoadingProposals(false);
    }
  }, [engagementId, statusFilter, selectedProposalId]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  // Fetch proposal details and audit history when selectedProposalId changes
  useEffect(() => {
    if (!engagementId || !selectedProposalId) {
      setSelectedProposal(null);
      setProposalHistory([]);
      return;
    }

    let cancelled = false;
    setIsHistoryLoading(true);

    fetchTriageProposal(engagementId, selectedProposalId)
      .then((p) => {
        if (!cancelled) setSelectedProposal(p);
      })
      .catch(() => {
        if (!cancelled) setSelectedProposal(null);
      });

    fetchProposalHistory(engagementId, selectedProposalId)
      .then((hist) => {
        if (!cancelled) setProposalHistory(hist);
      })
      .catch(() => {
        if (!cancelled) setProposalHistory([]);
      })
      .finally(() => {
        if (!cancelled) setIsHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [engagementId, selectedProposalId]);

  const handleProposalCreated = (created: TriageProposalResponse, _isDuplicate: boolean) => {
    setProposals((prev) => {
      const exists = prev.some((p) => p.id === created.id);
      if (exists) {
        return prev.map((p) => (p.id === created.id ? created : p));
      }
      return [created, ...prev];
    });
    setSelectedProposalId(created.id);
    setSelectedProposal(created);
  };

  const handleProposalUpdated = (updated: TriageProposalResponse) => {
    setProposals((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    setSelectedProposal(updated);

    if (engagementId) {
      setIsHistoryLoading(true);
      fetchProposalHistory(engagementId, updated.id)
        .then(setProposalHistory)
        .catch(() => {})
        .finally(() => setIsHistoryLoading(false));
    }
  };

  if (!activeEngagement) {
    return (
      <div className="space-y-6">
        <header className="space-y-1.5">
          <Eyebrow>Stage 03 · Build</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Prototypes
          </h1>
        </header>

        <EmptyState
          eyebrow="Stage 03 · Build"
          title="No triage proposals awaiting review"
          description="Run the support triage workflow to review agent categorisations, policy-grounded draft responses, and human approval history."
          icon={<FlaskConical size={16} strokeWidth={1.75} aria-hidden="true" />}
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Accessible Tablist */}
      <div
        role="tablist"
        aria-label="Prototypes views"
        className="flex items-center gap-2 border-b border-border pb-px"
      >
        <button
          type="button"
          role="tab"
          id="tab-triage"
          aria-selected={activeTab === "triage"}
          aria-controls="tabpanel-triage"
          tabIndex={activeTab === "triage" ? 0 : -1}
          onClick={() => handleTabChange("triage")}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") handleTabChange("evaluation");
          }}
          className={[
            "px-4 py-2 text-[14px] font-medium border-b-2 transition-colors",
            activeTab === "triage"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-muted hover:text-ink hover:border-border",
          ].join(" ")}
        >
          Triage workspace
        </button>

        <button
          type="button"
          role="tab"
          id="tab-evaluation"
          aria-selected={activeTab === "evaluation"}
          aria-controls="tabpanel-evaluation"
          tabIndex={activeTab === "evaluation" ? 0 : -1}
          onClick={() => handleTabChange("evaluation")}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") handleTabChange("triage");
          }}
          className={[
            "px-4 py-2 text-[14px] font-medium border-b-2 transition-colors",
            activeTab === "evaluation"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-muted hover:text-ink hover:border-border",
          ].join(" ")}
        >
          Agent evaluation
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "triage" ? (
        <div
          role="tabpanel"
          id="tabpanel-triage"
          aria-labelledby="tab-triage"
          className="space-y-6"
        >
          {/* Top Header & persistent banners */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Eyebrow>Stage 03 · Build</Eyebrow>
                <div className="flex items-center gap-2 mt-1">
                  <h1 className="text-xl font-serif font-bold text-neutral-900">
                    Support Triage Prototype
                  </h1>
                  <span className="inline-flex items-center gap-1 rounded bg-accent-soft text-accent border border-accent/25 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider">
                    <Sparkles size={11} aria-hidden="true" />
                    Deterministic Priority + AI Draft
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <SyntheticDataNotice />
                <span className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 text-amber-900 px-2.5 py-1 text-xs font-medium">
                  <ShieldAlert size={13} className="text-amber-700 shrink-0" aria-hidden="true" />
                  <span>Proposed actions only. Nothing is sent to customers.</span>
                </span>
              </div>
            </div>
          </div>

          {/* Main Two-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left Column: Ticket Submission & Proposal Inbox (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              <SubmitTicketForm
                engagementId={activeEngagement.id}
                llmConfigured={llmConfigured}
                onProposalCreated={handleProposalCreated}
              />

              <ProposalInbox
                proposals={proposals}
                selectedProposalId={selectedProposalId}
                onSelectProposal={setSelectedProposalId}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                isLoading={isLoadingProposals}
                onRefresh={loadProposals}
              />
            </div>

            {/* Right Column: Selected Proposal Detail, Trace, & Action History (7 cols) */}
            <div className="lg:col-span-7">
              {selectedProposal ? (
                <ProposalDetail
                  proposal={selectedProposal}
                  onProposalUpdated={handleProposalUpdated}
                  history={proposalHistory}
                  isHistoryLoading={isHistoryLoading}
                />
              ) : (
                <div className="rounded border border-neutral-200 bg-white p-12 text-center">
                  <EmptyState
                    title="No proposal selected"
                    description="Select a proposal from the inbox on the left or submit a new ticket to inspect AI recommendations, deterministic priority rules, draft responses, and audit history."
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div
          role="tabpanel"
          id="tabpanel-evaluation"
          aria-labelledby="tab-evaluation"
        >
          <EvaluationTab
            engagementId={activeEngagement.id}
            llmConfigured={llmConfigured}
          />
        </div>
      )}
    </div>
  );
}

export default PrototypesPage;
