import { Button, Card, Eyebrow, StatusPill } from "../ui";
import { formatShortDate } from "../../lib/format";
import type { EvalRunSummary } from "../../lib/api";

export interface RunHistoryProps {
  runs: EvalRunSummary[];
  selectedRunId?: number | null;
  onSelectRun: (runId: number) => void;
}

export function RunHistory({ runs, selectedRunId, onSelectRun }: RunHistoryProps) {
  if (!runs || runs.length === 0) return null;

  return (
    <Card className="p-6 space-y-4">
      <div>
        <Eyebrow>RUN ARCHIVE</Eyebrow>
        <h3 className="font-display text-[20px] font-normal text-ink">
          Evaluation History
        </h3>
        <p className="text-[12px] text-muted">
          Previous evaluation runs recorded for this engagement.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13px] border-collapse font-mono">
          <thead>
            <tr className="border-b border-border bg-surface-subtle text-muted text-[11px] uppercase font-semibold">
              <th className="p-2.5">Run ID</th>
              <th className="p-2.5">Date</th>
              <th className="p-2.5">Model</th>
              <th className="p-2.5 text-right">Sample (n)</th>
              <th className="p-2.5 text-right">Category Acc.</th>
              <th className="p-2.5 text-right">Priority Acc.</th>
              <th className="p-2.5 text-center">Status</th>
              <th className="p-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const isSelected = selectedRunId === r.id;
              const catAcc =
                r.results?.summary?.category_accuracy_pct !== undefined
                  ? `${r.results.summary.category_accuracy_pct}%`
                  : "-";
              const priAcc =
                r.results?.summary?.priority_accuracy_pct !== undefined
                  ? `${r.results.summary.priority_accuracy_pct}%`
                  : "-";

              return (
                <tr
                  key={r.id}
                  className={[
                    "border-b border-border/50 hover:bg-surface-subtle/50 transition-colors",
                    isSelected ? "bg-accent/5 font-medium" : "",
                  ].join(" ")}
                >
                  <td className="p-2.5 text-ink font-semibold">#{r.id}</td>
                  <td className="p-2.5 text-muted text-[12px]">
                    {formatShortDate(r.created_at)}
                  </td>
                  <td className="p-2.5 text-ink text-[12px] truncate max-w-[160px]">
                    {r.model}
                  </td>
                  <td className="p-2.5 text-right tabular-nums text-muted">
                    {r.sample_size}
                  </td>
                  <td className="p-2.5 text-right tabular-nums text-ink">{catAcc}</td>
                  <td className="p-2.5 text-right tabular-nums text-ink">{priAcc}</td>
                  <td className="p-2.5 text-center font-sans">
                    <StatusPill
                      variant={
                        r.status === "completed"
                          ? "success"
                          : r.status === "running"
                          ? "info"
                          : r.status === "paused"
                          ? "warning"
                          : "neutral"
                      }
                      label={r.status}
                    />
                  </td>
                  <td className="p-2.5 text-right font-sans">
                    <Button
                      variant={isSelected ? "secondary" : "tertiary"}
                      onClick={() => onSelectRun(r.id)}
                      className="text-[12px] px-2.5 py-1"
                    >
                      {isSelected ? "Active" : "View"}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
