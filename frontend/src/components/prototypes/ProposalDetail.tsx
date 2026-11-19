import { AlertTriangle, BookOpen, Clock, FileText, Sparkles, Tag } from "lucide-react";
import { TypeLabel } from "../ui/TypeLabel";
import { StatusPill } from "../ui/StatusPill";
import { SignalList } from "./SignalList";
import { ReplyEditor } from "./ReplyEditor";
import { DecisionControls } from "./DecisionControls";
import { PipelineTrace } from "./PipelineTrace";
import { ActionHistory } from "./ActionHistory";
import type { AuditLogEntry, TriageProposalResponse } from "../../lib/api";

export interface ProposalDetailProps {
  proposal: TriageProposalResponse;
  onProposalUpdated: (updated: TriageProposalResponse) => void;
  history: AuditLogEntry[];
  isHistoryLoading?: boolean;
}

export function ProposalDetail({
  proposal,
  onProposalUpdated,
  history,
  isHistoryLoading = false,
}: ProposalDetailProps) {
  const getPriorityVariant = (priority: string) => {
    switch (priority?.toLowerCase()) {
      case "high":
        return "danger" as const;
      case "medium":
        return "warning" as const;
      default:
        return "neutral" as const;
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "approved":
        return "success" as const;
      case "rejected":
        return "danger" as const;
      default:
        return "warning" as const;
    }
  };

  const formatStatusLabel = (status: string) => {
    switch (status) {
      case "awaiting_approval":
        return "Awaiting approval";
      case "approved":
        return "Approved";
      case "rejected":
        return "Rejected";
      default:
        return status;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="rounded border border-neutral-200 bg-white p-4 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-neutral-400">
              Proposal #{proposal.id}
            </span>
            <span className="text-neutral-300">|</span>
            <span className="font-mono text-xs text-neutral-600 bg-neutral-100 px-2 py-0.5 rounded">
              Channel: {proposal.channel || "web_form"}
            </span>
            {proposal.escalation && (
              <span className="text-[10px] font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded uppercase tracking-wider">
                Escalation
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <StatusPill
              variant={getStatusVariant(proposal.status)}
              label={formatStatusLabel(proposal.status)}
            />
            <span className="text-xs text-neutral-400 font-mono flex items-center gap-1">
              <Clock size={12} aria-hidden="true" />
              {new Date(proposal.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        <h1 className="text-base font-semibold text-neutral-900">
          {proposal.subject || "Untitled Customer Inquiry"}
        </h1>
      </div>

      {/* Inbound Ticket Content (Untrusted Data) */}
      <div className="rounded border border-neutral-200 bg-white p-4 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-neutral-700">
            <FileText size={14} className="text-neutral-500" aria-hidden="true" />
            <span>Customer Inquiry Body</span>
            <span className="text-[10px] uppercase font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.2 rounded">
              Untrusted Input
            </span>
          </div>
          <span className="text-[11px] font-mono text-neutral-400">
            {(proposal.body || "").length} chars
          </span>
        </div>
        <div className="rounded border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-800 leading-relaxed font-sans whitespace-pre-wrap select-text">
          {proposal.body || ""}
        </div>
      </div>

      {/* AI Recommendation Card */}
      <div className="rounded border border-neutral-200 bg-white p-4 space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-sky-600" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-neutral-900">Proposed Triage Assessment</h2>
          </div>
          <TypeLabel type="AI recommendation" />
        </div>

        {/* Classification and Routing Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-2.5 rounded border border-neutral-200 bg-neutral-50 space-y-1">
            <div className="flex items-center gap-1 text-[11px] font-medium text-neutral-500 uppercase tracking-wider">
              <Tag size={11} aria-hidden="true" />
              <span>Category</span>
            </div>
            <div className="font-mono font-semibold text-neutral-900">{proposal.category}</div>
            {proposal.secondary_category && (
              <div className="text-[11px] text-neutral-500">
                Secondary: <span className="font-mono text-neutral-700">{proposal.secondary_category}</span>
              </div>
            )}
          </div>

          <div className="p-2.5 rounded border border-neutral-200 bg-neutral-50 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider">
                Recommended Priority
              </span>
              <StatusPill
                variant={getPriorityVariant(proposal.priority)}
                label={proposal.priority}
              />
            </div>
            <div className="text-[11px] text-neutral-700 pt-1">
              <span className="font-semibold text-neutral-900">Deterministic rule:</span>{" "}
              <span className="font-mono font-medium text-sky-800">{proposal.rule_id || "R-DEFAULT"}</span>
              {proposal.rule_definition && (
                <p className="text-[11px] text-neutral-600 mt-0.5 leading-snug">
                  {proposal.rule_definition}
                </p>
              )}
            </div>
          </div>

          <div className="p-2.5 rounded border border-neutral-200 bg-neutral-50 space-y-1">
            <span className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider block">
              Assigned Queue
            </span>
            <div className="font-semibold text-neutral-900">{proposal.queue}</div>
            {proposal.escalation && (
              <span className="inline-block text-[10px] text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded font-medium">
                Escalations override applied
              </span>
            )}
          </div>
        </div>

        {/* Signals Section */}
        <div className="space-y-1.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-600">
            Detected Signals & Quotes
          </h3>
          <SignalList signals={proposal.signals} />
        </div>

        {/* AI Rationale */}
        {proposal.rationale && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-600">
                AI Classification Rationale
              </h3>
              <TypeLabel type="Hypothesis" />
            </div>
            <p className="text-xs text-neutral-700 leading-relaxed bg-neutral-50 p-2.5 rounded border border-neutral-200 italic">
              {proposal.rationale}
            </p>
          </div>
        )}

        {/* Review Flags */}
        {proposal.flags && proposal.flags.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-700">
              <AlertTriangle size={13} aria-hidden="true" />
              <span>Review Flags ({proposal.flags.length})</span>
            </div>
            <div className="space-y-1">
              {proposal.flags.map((flag, idx) => (
                <div
                  key={`${flag.code}-${idx}`}
                  className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900 flex items-start gap-2"
                >
                  <span className="font-mono text-[11px] bg-amber-100 text-amber-900 px-1 py-0.5 rounded shrink-0 font-medium">
                    {flag.code}
                  </span>
                  <span className="leading-snug">{flag.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Policy References */}
        {proposal.policy_refs && proposal.policy_refs.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-neutral-600">
              <BookOpen size={13} aria-hidden="true" />
              <span>Cited Policy Documents</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {proposal.policy_refs.map((ref) => (
                <span
                  key={ref}
                  className="text-xs bg-neutral-100 text-neutral-800 px-2 py-0.5 rounded border border-neutral-200 font-medium"
                >
                  {ref}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Reviewer Note */}
        {proposal.reviewer_note && (
          <div className="p-2.5 rounded border border-neutral-200 bg-neutral-50 text-xs text-neutral-700 space-y-0.5">
            <span className="font-semibold text-neutral-900 text-[11px] uppercase tracking-wider block">
              AI Note for Human Reviewer
            </span>
            <p className="italic text-neutral-600">{proposal.reviewer_note}</p>
          </div>
        )}

        {/* Draft Response Area */}
        <ReplyEditor
          reply={proposal.draft_reply}
          readOnly={true}
        />

        {/* Decision Controls */}
        <DecisionControls
          proposal={proposal}
          onDecisionRecorded={onProposalUpdated}
        />
      </div>

      {/* Execution Trace */}
      <PipelineTrace steps={proposal.tool_trace} />

      {/* Action History */}
      <ActionHistory history={history} isLoading={isHistoryLoading} />
    </div>
  );
}
