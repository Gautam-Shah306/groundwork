import { History, CheckCircle2, XCircle, Sparkles, User } from "lucide-react";
import type { AuditLogEntry } from "../../lib/api";

export interface ActionHistoryProps {
  history: AuditLogEntry[];
  isLoading?: boolean;
}

export function ActionHistory({ history, isLoading = false }: ActionHistoryProps) {
  const list = Array.isArray(history) ? history : [];

  if (isLoading) {
    return (
      <div className="py-4 text-center text-xs text-neutral-400">Loading action history...</div>
    );
  }

  if (list.length === 0) {
    return (
      <p className="text-xs text-neutral-500 italic">No recorded actions for this proposal yet.</p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-neutral-500">
        <History size={13} aria-hidden="true" />
        <span>Action History ({list.length} event{list.length > 1 ? "s" : ""})</span>
      </div>

      <div className="rounded border border-neutral-200 bg-white divide-y divide-neutral-100 text-xs">
        {list.map((entry) => {
          const isApproval = entry.action === "triage.proposal_approved";
          const isRejection = entry.action === "triage.proposal_rejected";
          const isCreation = entry.action === "triage.proposal_created";
          const d = entry.details || {};

          return (
            <div key={entry.id} className="p-3 space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 font-medium text-neutral-800">
                  {isApproval && <CheckCircle2 size={13} className="text-emerald-600 shrink-0" aria-hidden="true" />}
                  {isRejection && <XCircle size={13} className="text-rose-600 shrink-0" aria-hidden="true" />}
                  {isCreation && <Sparkles size={13} className="text-sky-600 shrink-0" aria-hidden="true" />}
                  {!isApproval && !isRejection && !isCreation && (
                    <User size={13} className="text-neutral-500 shrink-0" aria-hidden="true" />
                  )}
                  <span className="font-mono text-[11px] font-semibold text-neutral-900">{entry.action}</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-neutral-400">
                  <span className="font-mono">by {entry.actor}</span>
                  <span>{new Date(entry.created_at).toLocaleString()}</span>
                </div>
              </div>

              {/* Detailed diff or changes */}
              <div className="text-[11px] text-neutral-600 pl-4 border-l-2 border-neutral-200 ml-1 space-y-1">
                {isCreation && (
                  <div>
                    Proposed: <span className="font-medium text-neutral-800">{String(d.proposed_category || "")}</span> (
                    {String(d.proposed_priority || "")} priority, {String(d.proposed_queue || "")} queue)
                  </div>
                )}

                {isApproval && (
                  <div className="space-y-0.5">
                    <div>
                      <span className="font-semibold text-emerald-800">Approved</span>
                      {d.edited ? " (with human edits)" : " (as proposed)"}
                    </div>
                    {Boolean(d.edited) && Array.isArray(d.edited_fields) && d.edited_fields.length > 0 && (
                      <div className="text-neutral-500">
                        Edited fields: <span className="font-mono text-neutral-700">{d.edited_fields.join(", ")}</span>
                      </div>
                    )}
                    {Boolean(d.priority_overridden) && (
                      <div className="text-amber-800 font-medium">
                        Priority override: {String(d.original_priority || "")} &rarr; {String(d.final_priority || "")}
                      </div>
                    )}
                  </div>
                )}

                {isRejection && (
                  <div className="space-y-0.5">
                    <div className="font-semibold text-rose-800">Rejected</div>
                    {typeof d.reason === "string" && d.reason.trim() && (
                      <div className="italic text-neutral-600">&ldquo;{d.reason}&rdquo;</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
