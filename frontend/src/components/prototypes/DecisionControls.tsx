import { useState } from "react";
import { CheckCircle2, XCircle, Edit3, AlertCircle, ShieldAlert } from "lucide-react";
import { Button } from "../ui/Button";
import { ReplyEditor } from "./ReplyEditor";
import {
  recordProposalDecision,
  type PriorityLevel,
  type ProposalDecisionPayload,
  type TriageProposalResponse,
} from "../../lib/api";

export interface DecisionControlsProps {
  proposal: TriageProposalResponse;
  onDecisionRecorded: (updated: TriageProposalResponse) => void;
}

const DEFAULT_CATEGORIES = [
  "order_tracking",
  "damaged_item",
  "address_change",
  "returns_refunds",
  "payment_issues",
  "product_questions",
  "cancellation",
  "account_access",
  "feedback_complaint",
];

const DEFAULT_QUEUES = [
  "Order support",
  "Returns and refunds",
  "Payments",
  "General",
  "Escalations",
];

const PLACEHOLDER_REGEX = /\[[A-Za-z0-9_]+\]/g;

export function DecisionControls({ proposal, onDecisionRecorded }: DecisionControlsProps) {
  const isDecided = proposal.status !== "awaiting_approval";

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editedCategory, setEditedCategory] = useState(proposal.category);
  const [editedPriority, setEditedPriority] = useState<PriorityLevel>(
    (proposal.priority as PriorityLevel) || "medium"
  );
  const [editedQueue, setEditedQueue] = useState(proposal.queue);
  const [editedReply, setEditedReply] = useState(proposal.draft_reply || "");

  // Modal / Confirm state
  const [confirmingAction, setConfirmingAction] = useState<"approve" | "reject" | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If already decided, show persistent summary
  if (isDecided) {
    const isApproved = proposal.status === "approved";
    return (
      <div
        className={`rounded border p-3 text-xs space-y-1.5 ${
          isApproved
            ? "border-emerald-200 bg-emerald-50/60 text-emerald-900"
            : "border-rose-200 bg-rose-50/60 text-rose-900"
        }`}
      >
        <div className="flex items-center gap-2 font-semibold">
          {isApproved ? (
            <CheckCircle2 size={15} className="text-emerald-700 shrink-0" aria-hidden="true" />
          ) : (
            <XCircle size={15} className="text-rose-700 shrink-0" aria-hidden="true" />
          )}
          <span>
            Proposal {isApproved ? "Approved" : "Rejected"}
            {proposal.edited ? " (with edits)" : ""}
          </span>
        </div>
        <div className="text-[11px] opacity-80">
          Decided by {proposal.decided_by || "operator"} on{" "}
          {proposal.decided_at ? new Date(proposal.decided_at).toLocaleString() : "recently"}.
        </div>
        {proposal.decision_reason && (
          <div className="text-[11px] italic mt-1">Reason: &ldquo;{proposal.decision_reason}&rdquo;</div>
        )}
        {proposal.final_values && (
          <div className="mt-2 pt-2 border-t border-emerald-200/60 text-[11px] space-y-0.5">
            <span className="font-semibold block uppercase tracking-wider text-[10px]">
              Final Recorded Values
            </span>
            <div>Category: {proposal.final_values.category}</div>
            <div>Priority: {proposal.final_values.priority}</div>
            <div>Queue: {proposal.final_values.queue}</div>
          </div>
        )}
      </div>
    );
  }

  const activeReply = isEditing ? editedReply : proposal.draft_reply || "";
  const unresolvedPlaceholders = activeReply.match(PLACEHOLDER_REGEX) || [];

  const handleApprove = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const payload: ProposalDecisionPayload = {
        decision: "approve",
        final: {
          category: isEditing ? editedCategory : proposal.category,
          priority: isEditing ? editedPriority : (proposal.priority as PriorityLevel),
          queue: isEditing ? editedQueue : proposal.queue,
          reply_text: activeReply,
        },
      };

      const res = await recordProposalDecision(proposal.engagement_id, proposal.id, payload);
      setIsEditing(false);
      setConfirmingAction(null);

      // Mutate local proposal object copy to update parent immediately
      const updated: TriageProposalResponse = {
        ...proposal,
        status: res.status as "approved",
        edited: res.edited,
        decided_by: res.decided_by,
        decided_at: res.decided_at,
        final_values: payload.final,
      };
      onDecisionRecorded(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const payload: ProposalDecisionPayload = {
        decision: "reject",
        reason: rejectReason.trim() || undefined,
      };

      const res = await recordProposalDecision(proposal.engagement_id, proposal.id, payload);
      setIsEditing(false);
      setConfirmingAction(null);

      const updated: TriageProposalResponse = {
        ...proposal,
        status: res.status as "rejected",
        decided_by: res.decided_by,
        decided_at: res.decided_at,
        decision_reason: rejectReason.trim() || undefined,
      };
      onDecisionRecorded(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-3 pt-3 border-t border-neutral-200">
      {errorMessage && (
        <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle size={14} className="text-rose-600 shrink-0" aria-hidden="true" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Edit Form */}
      {isEditing && (
        <div className="rounded border border-neutral-200 bg-neutral-50/70 p-3 space-y-3 text-xs">
          <div className="font-semibold text-neutral-800 flex items-center gap-1.5">
            <Edit3 size={13} aria-hidden="true" />
            <span>Human Override / Edit Proposal</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div>
              <label htmlFor="edit-category-select" className="block text-[11px] font-medium text-neutral-600 mb-1">
                Category
              </label>
              <select
                id="edit-category-select"
                value={editedCategory}
                onChange={(e) => setEditedCategory(e.target.value)}
                className="w-full rounded border border-neutral-300 bg-white p-1.5 text-xs text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400"
              >
                {DEFAULT_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="edit-priority-select" className="block text-[11px] font-medium text-neutral-600 mb-1">
                Priority
              </label>
              <select
                id="edit-priority-select"
                value={editedPriority}
                onChange={(e) => setEditedPriority(e.target.value as PriorityLevel)}
                className="w-full rounded border border-neutral-300 bg-white p-1.5 text-xs text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400"
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>

            <div>
              <label htmlFor="edit-queue-select" className="block text-[11px] font-medium text-neutral-600 mb-1">
                Target Queue
              </label>
              <select
                id="edit-queue-select"
                value={editedQueue}
                onChange={(e) => setEditedQueue(e.target.value)}
                className="w-full rounded border border-neutral-300 bg-white p-1.5 text-xs text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400"
              >
                {DEFAULT_QUEUES.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <ReplyEditor reply={editedReply} onChange={setEditedReply} />

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsEditing(false);
                setEditedCategory(proposal.category);
                setEditedPriority((proposal.priority as PriorityLevel) || "medium");
                setEditedQueue(proposal.queue);
                setEditedReply(proposal.draft_reply || "");
              }}
            >
              Cancel Edit
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => setConfirmingAction("approve")}
            >
              Save & Approve
            </Button>
          </div>
        </div>
      )}

      {/* Confirmation Dialog / Step */}
      {confirmingAction === "approve" && (
        <div className="rounded border border-emerald-300 bg-emerald-50/90 p-3 space-y-2.5 text-xs text-emerald-950">
          <div className="flex items-start gap-2">
            <ShieldAlert size={16} className="text-emerald-700 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1">
              <span className="font-semibold block text-emerald-900">
                Confirm Human Approval Decision
              </span>
              <p className="text-[11px] text-emerald-800 leading-normal">
                Approving records your verified decision in the audit log. Remember: Groundwork produces
                proposed actions only; nothing is sent to customers.
              </p>
              {unresolvedPlaceholders.length > 0 && (
                <div className="p-2 rounded bg-amber-100 border border-amber-300 text-amber-900 text-[11px] mt-1.5">
                  <span className="font-semibold">Notice:</span> {unresolvedPlaceholders.length} unresolved
                  placeholder(s) remain in the reply: {unresolvedPlaceholders.join(", ")}.
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="secondary"
              disabled={isSubmitting}
              onClick={() => setConfirmingAction(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={isSubmitting}
              onClick={handleApprove}
            >
              {isSubmitting ? "Recording..." : "Confirm Approval"}
            </Button>
          </div>
        </div>
      )}

      {confirmingAction === "reject" && (
        <div className="rounded border border-rose-300 bg-rose-50/90 p-3 space-y-2.5 text-xs text-rose-950">
          <div className="flex items-start gap-2">
            <XCircle size={16} className="text-rose-700 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1 w-full">
              <span className="font-semibold block text-rose-900">
                Reject Proposal
              </span>
              <p className="text-[11px] text-rose-800">
                Provide an optional reason for rejecting this AI triage proposal.
              </p>
              <input
                type="text"
                maxLength={300}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Optional rejection reason (max 300 chars)..."
                className="w-full rounded border border-rose-300 bg-white p-1.5 text-xs text-neutral-800 mt-1 focus:outline-none focus:ring-1 focus:ring-rose-400"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="secondary"
              disabled={isSubmitting}
              onClick={() => setConfirmingAction(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={isSubmitting}
              onClick={handleReject}
            >
              {isSubmitting ? "Rejecting..." : "Confirm Rejection"}
            </Button>
          </div>
        </div>
      )}

      {/* Main Buttons Bar */}
      {!isEditing && !confirmingAction && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="primary"
              onClick={() => setConfirmingAction("approve")}
            >
              Approve proposal
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsEditing(true)}
            >
              <Edit3 size={12} className="mr-1" aria-hidden="true" />
              Edit proposal
            </Button>
          </div>
          <Button
            type="button"
            variant="destructive"
            onClick={() => setConfirmingAction("reject")}
          >
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}
