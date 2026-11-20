import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button, Card, Eyebrow, StatusPill } from "../ui";
import type { EvalItem, EvalResults } from "../../lib/api";

export interface FailureCasesListProps {
  failureCases: EvalResults["failure_cases"];
  onViewAllFailed?: () => void;
  failedItems?: EvalItem[];
  isLoadingFailedItems?: boolean;
}

export function FailureCasesList({
  failureCases,
  onViewAllFailed,
  failedItems = [],
  isLoadingFailedItems = false,
}: FailureCasesListProps) {
  const [showAllFailed, setShowAllFailed] = useState(false);

  if (!failureCases || failureCases.length === 0) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-success">
          <p className="text-[14px] font-medium">
            Zero priority or classification failures in this evaluation sample!
          </p>
        </div>
      </Card>
    );
  }

  const handleToggleAll = () => {
    if (!showAllFailed && onViewAllFailed) {
      onViewAllFailed();
    }
    setShowAllFailed(!showAllFailed);
  };

  return (
    <Card className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>DIAGNOSTIC INSPECTION</Eyebrow>
          <h3 className="font-display text-[20px] font-normal text-ink">
            Top Failure Cases
          </h3>
          <p className="text-[12px] text-muted">
            Prioritized by operational severity (Missed High &gt; Wrong Category &gt; Wrong Priority &gt; Failed Items).
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

      {/* Top 5 Cards */}
      <div className="space-y-3">
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
                <span className="text-muted block text-[11px]">Category Comparison</span>
                <span className="font-mono text-ink">
                  {caseItem.true_category}{" "}
                  <span className="text-muted font-sans">→ predicted:</span>{" "}
                  <strong className={caseItem.predicted_category === caseItem.true_category ? "text-success" : "text-warning"}>
                    {caseItem.predicted_category || "None"}
                  </strong>
                </span>
              </div>

              <div>
                <span className="text-muted block text-[11px]">Priority Comparison</span>
                <span className="font-mono text-ink">
                  {caseItem.true_priority}{" "}
                  <span className="text-muted font-sans">→ predicted:</span>{" "}
                  <strong className={caseItem.predicted_priority === caseItem.true_priority ? "text-success" : "text-warning"}>
                    {caseItem.predicted_priority || "None"}
                  </strong>
                </span>
              </div>
            </div>

            {/* Snippet */}
            <div className="text-[12px] text-muted bg-surface-subtle p-2 rounded border border-border/40 font-mono">
              "{caseItem.body_snippet}…"
            </div>
          </div>
        ))}
      </div>

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
  );
}
