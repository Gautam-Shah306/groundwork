import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button, Card, Eyebrow, StatusPill } from "../ui";
import type { EvalItem, EvalResults } from "../../lib/api";

export interface FailureCasesListProps {
  failureCases: EvalResults["failure_cases"];
  draftChecks?: EvalResults["draft_checks"];
  onViewAllFailed?: () => void;
  failedItems?: EvalItem[];
  isLoadingFailedItems?: boolean;
}

export function FailureCasesList({
  failureCases,
  draftChecks,
  onViewAllFailed,
  failedItems = [],
  isLoadingFailedItems = false,
}: FailureCasesListProps) {
  const [showAllFailed, setShowAllFailed] = useState(false);

  const handleToggleAll = () => {
    if (!showAllFailed && onViewAllFailed) {
      onViewAllFailed();
    }
    setShowAllFailed(!showAllFailed);
  };

  return (
    <div className="space-y-6">
      {/* Top Failure Cases Card */}
      <Card className="p-6 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Eyebrow>DIAGNOSTIC INSPECTION</Eyebrow>
            <h3 className="font-display text-[20px] font-normal text-ink">
              Top Failure Cases (Up to 5)
            </h3>
            <p className="text-[12px] text-muted">
              Prioritized deterministically by operational severity (Missed High &gt; Wrong Category &gt; Wrong Priority &gt; No Prediction).
            </p>
          </div>

          {onViewAllFailed && (
            <Button
              variant="tertiary"
              onClick={handleToggleAll}
              className="text-[13px] text-accent hover:text-accent-hover"
            >
              {showAllFailed ? (
                <>
                  Hide full failure list
                  <ChevronUp size={14} className="ml-1" />
                </>
              ) : (
                <>
                  View all failed tickets
                  <ChevronDown size={14} className="ml-1" />
                </>
              )}
            </Button>
          )}
        </div>

        {(!failureCases || failureCases.length === 0) ? (
          <div className="text-[14px] text-success font-medium p-4 bg-success-soft/30 rounded-card">
            Zero priority or classification failures in this evaluation sample!
          </div>
        ) : (
          <div className="space-y-4">
            {failureCases.map((caseItem, idx) => (
              <div
                key={caseItem.ticket_id}
                className="rounded-card border border-border/80 bg-surface p-4 space-y-3 hover:border-border transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[12px] font-semibold text-ink">
                      #{idx + 1} {caseItem.ticket_id}
                    </span>
                    {caseItem.subject && (
                      <span className="text-[13px] text-muted truncate max-w-[280px]">
                        "{caseItem.subject}"
                      </span>
                    )}
                  </div>

                  <span className="text-[11px] font-medium text-warning bg-warning-soft px-2 py-0.5 rounded-full border border-warning/20">
                    {caseItem.reason}
                  </span>
                </div>

                {/* Comparison Grid */}
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-[12px]">
                  <div>
                    <span className="text-muted block text-[11px]">Category</span>
                    <span className="font-mono text-ink">
                      True: <strong>{caseItem.true_category}</strong> → Predicted:{" "}
                      <strong className={caseItem.predicted_category === caseItem.true_category ? "text-success" : "text-warning"}>
                        {caseItem.predicted_category || "None"}
                      </strong>
                    </span>
                  </div>

                  <div>
                    <span className="text-muted block text-[11px]">Priority</span>
                    <span className="font-mono text-ink">
                      True: <strong>{caseItem.true_priority}</strong> → Predicted:{" "}
                      <strong className={caseItem.predicted_priority === caseItem.true_priority ? "text-success" : "text-warning"}>
                        {caseItem.predicted_priority || "None"}
                      </strong>
                    </span>
                  </div>
                </div>

                {/* Signals Comparison */}
                <div className="text-[11px] font-mono text-muted space-y-1">
                  <div>
                    <span className="font-semibold text-ink">True Signals:</span>{" "}
                    {caseItem.true_signals?.length ? caseItem.true_signals.join(", ") : "None"}
                  </div>
                  <div>
                    <span className="font-semibold text-ink">Pred Signals:</span>{" "}
                    {caseItem.predicted_signals?.length ? caseItem.predicted_signals.join(", ") : "None"}
                  </div>
                </div>

                {/* Ticket Text strictly as plain text */}
                <div className="text-[12px] text-muted bg-surface-subtle p-3 rounded border border-border/40 font-mono whitespace-pre-wrap">
                  {caseItem.body || caseItem.body_snippet}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Expanded All Failures View */}
        {showAllFailed && (
          <div className="mt-6 pt-6 border-t border-border space-y-4">
            <h4 className="text-[14px] font-semibold text-ink">
              All Failed Evaluation Tickets ({failedItems.length})
            </h4>

            {isLoadingFailedItems ? (
              <p className="text-[12px] text-muted">Loading failed items...</p>
            ) : (
              <div className="overflow-x-auto max-h-[400px]">
                <table className="w-full text-left text-[12px] border-collapse font-mono">
                  <thead>
                    <tr className="border-b border-border bg-surface-subtle text-muted text-[11px] uppercase font-semibold">
                      <th className="p-2">ID</th>
                      <th className="p-2">Status</th>
                      <th className="p-2">Pred Category</th>
                      <th className="p-2">Pred Priority</th>
                      <th className="p-2">Error / Flags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {failedItems.map((it) => (
                      <tr key={it.id} className="border-b border-border/40 hover:bg-surface-subtle">
                        <td className="p-2 font-medium text-ink">{it.ticket_id}</td>
                        <td className="p-2">
                          <StatusPill
                            variant={it.status === "success" ? "warning" : "danger"}
                            label={it.status}
                          />
                        </td>
                        <td className="p-2 text-ink">{it.predicted_category || "-"}</td>
                        <td className="p-2 text-ink">{it.predicted_priority || "-"}</td>
                        <td className="p-2 text-muted text-[11px]">
                          {it.error_code || `${it.flags?.length || 0} flags`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Draft Check Section (rendered only when drafts were sampled) - A5/A6 */}
      {draftChecks && (
        <Card className="p-6 space-y-4">
          <div>
            <Eyebrow>RESPONSE INTEGRITY VERIFICATION</Eyebrow>
            <h3 className="font-display text-[20px] font-normal text-ink">
              Sample Draft Reply Quality Checks
            </h3>
            <p className="text-[12px] text-muted">
              Automated review flags evaluated on a sample of completed ticket drafts.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="p-3 bg-surface-subtle rounded border border-border">
              <span className="text-[11px] text-muted uppercase font-semibold block">Drafts Sampled</span>
              <span className="font-mono text-[20px] font-bold text-ink">{draftChecks.n || draftChecks.count || 0}</span>
            </div>
            <div className="p-3 bg-surface-subtle rounded border border-border">
              <span className="text-[11px] text-muted uppercase font-semibold block">Flagged Drafts</span>
              <span className="font-mono text-[20px] font-bold text-warning">{draftChecks.tickets_with_flags ?? 0}</span>
            </div>
            <div className="p-3 bg-surface-subtle rounded border border-border">
              <span className="text-[11px] text-muted uppercase font-semibold block">Flag Rate</span>
              <span className="font-mono text-[20px] font-bold text-ink">
                {Math.round((draftChecks.flag_rate ?? 0) * 1000) / 10}%
              </span>
            </div>
            <div className="p-3 bg-surface-subtle rounded border border-border">
              <span className="text-[11px] text-muted uppercase font-semibold block">Draft Unavailable</span>
              <span className="font-mono text-[20px] font-bold text-muted">{draftChecks.draft_unavailable_count ?? 0}</span>
            </div>
          </div>

          {/* Counts by flag code */}
          {draftChecks.flag_counts_by_code && Object.keys(draftChecks.flag_counts_by_code).length > 0 && (
            <div className="space-y-2 pt-2">
              <h4 className="text-[12px] font-semibold text-ink uppercase tracking-wider">Flag Occurrences by Code</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(draftChecks.flag_counts_by_code).map(([code, count]) => (
                  <span
                    key={code}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-warning-soft/70 border border-warning/20 text-[12px] font-mono text-warning"
                  >
                    <span>{code}:</span>
                    <strong>{count}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Fixed mandatory note */}
          <div className="text-[12px] text-muted bg-surface-subtle p-2.5 rounded border border-border/60">
            {draftChecks.note || "Automated checks only: this does not measure reply quality."}
          </div>
        </Card>
      )}
    </div>
  );
}
