import { Inbox, RefreshCw } from "lucide-react";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { StatusPill } from "../ui/StatusPill";
import type { TriageProposalResponse } from "../../lib/api";

export interface ProposalInboxProps {
  proposals: TriageProposalResponse[];
  selectedProposalId: number | null;
  onSelectProposal: (proposalId: number) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  isLoading?: boolean;
  onRefresh?: () => void;
}

export function ProposalInbox({
  proposals,
  selectedProposalId,
  onSelectProposal,
  statusFilter,
  onStatusFilterChange,
  isLoading = false,
  onRefresh,
}: ProposalInboxProps) {
  const filterTabs = [
    { id: "all", label: "All" },
    { id: "awaiting_approval", label: "Awaiting approval" },
    { id: "approved", label: "Approved" },
    { id: "rejected", label: "Rejected" },
  ];

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
    <div className="rounded border border-neutral-200 bg-white p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Inbox size={15} className="text-neutral-500" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-neutral-900">Proposal Inbox</h2>
          <span className="text-xs text-neutral-400 font-mono">({proposals.length})</span>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="inline-flex rounded-control border border-neutral-200 p-0.5 bg-neutral-50 text-[11px]">
            {filterTabs.map((tab) => {
              const active = statusFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onStatusFilterChange(tab.id)}
                  className={`px-2 py-0.5 rounded font-medium transition-colors ${
                    active
                      ? "bg-white text-neutral-900 shadow-sm"
                      : "text-neutral-500 hover:text-neutral-800"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {onRefresh && (
            <Button
              type="button"
              variant="secondary"
              disabled={isLoading}
              onClick={onRefresh}
              aria-label="Refresh inbox"
              className="p-1.5 h-auto text-neutral-500 hover:text-neutral-800"
            >
              <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-neutral-400">Loading proposals...</div>
      ) : proposals.length === 0 ? (
        <EmptyState
          title="No proposals found"
          description="Submit an inbound ticket above to generate your first triage proposal."
        />
      ) : (
        <div className="rounded border border-neutral-200 overflow-hidden text-xs">
          <table className="w-full text-left divide-y divide-neutral-200">
            <thead className="bg-neutral-50 text-[11px] font-medium text-neutral-500">
              <tr>
                <th scope="col" className="px-3 py-2">Subject / Inquiry</th>
                <th scope="col" className="px-3 py-2">Category</th>
                <th scope="col" className="px-3 py-2">Priority</th>
                <th scope="col" className="px-3 py-2">Queue</th>
                <th scope="col" className="px-3 py-2">Status</th>
                <th scope="col" className="px-3 py-2 text-right">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 bg-white">
              {proposals.map((p) => {
                const isSelected = selectedProposalId === p.id;
                const displaySubject = p.subject || p.body.slice(0, 45) + (p.body.length > 45 ? "..." : "");
                return (
                  <tr
                    key={p.id}
                    onClick={() => onSelectProposal(p.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-sky-50/70 hover:bg-sky-50 font-medium"
                        : "hover:bg-neutral-50"
                    }`}
                  >
                    <td className="px-3 py-2.5 max-w-[200px] truncate text-neutral-900 font-medium">
                      {displaySubject}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-neutral-600">
                      {p.category}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusPill
                        variant={getPriorityVariant(p.priority)}
                        label={p.priority}
                      />
                    </td>
                    <td className="px-3 py-2.5 text-neutral-700">
                      {p.queue}
                      {p.escalation && (
                        <span className="ml-1 text-[10px] text-rose-600 font-semibold uppercase">
                          (Escalated)
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusPill
                        variant={getStatusVariant(p.status)}
                        label={formatStatusLabel(p.status)}
                      />
                    </td>
                    <td className="px-3 py-2.5 text-right text-[11px] text-neutral-400 font-mono">
                      {new Date(p.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
