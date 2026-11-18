import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Card,
  DataTable,
  StatusPill,
  TypeLabel,
  type DataTableColumn,
} from "../ui";
import type { ValidationCheckReport, ValidationReport } from "../../lib/api";

const SCOPE_LABELS: Record<string, string> = {
  all_metrics: "All metrics",
  response_metrics: "Response metrics",
  resolution_metrics: "Resolution metrics",
  triage_metrics: "Triage metrics",
};

function formatAffects(affects: string[]): string {
  if (affects.length === 0) {
    return "None (warning only)";
  }
  return affects.map((scope) => SCOPE_LABELS[scope] ?? scope).join(", ");
}

export interface ValidationSummaryProps {
  report: ValidationReport;
  showPassedChecks: boolean;
  expandedChecks: Record<string, boolean>;
  onToggleShowPassed: (show: boolean) => void;
  onToggleExamples: (code: string) => void;
  onSelectCheck: (check: ValidationCheckReport) => void;
}

export function ValidationSummary({
  report,
  showPassedChecks,
  expandedChecks,
  onToggleShowPassed,
  onToggleExamples,
  onSelectCheck,
}: ValidationSummaryProps) {
  const allChecks = report.checks ?? [];
  const visibleChecks = showPassedChecks
    ? allChecks
    : allChecks.filter((check) => check.count > 0);
  const passedCount = allChecks.filter((check) => check.count === 0).length;

  const checkColumns: DataTableColumn<
    ValidationCheckReport & Record<string, unknown>
  >[] = [
    {
      key: "code",
      header: "Check",
      render: (row) => {
        const isExpanded = Boolean(expandedChecks[row.code]);
        const hasExamples = row.examples.length > 0;
        return (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              {hasExamples && (
                <button
                  type="button"
                  aria-expanded={isExpanded}
                  aria-label={`Toggle examples for ${row.code}`}
                  onClick={() => onToggleExamples(row.code)}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-control border border-border bg-surface text-muted hover:bg-surface-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  {isExpanded ? (
                    <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" />
                  ) : (
                    <ChevronRight size={14} strokeWidth={1.75} aria-hidden="true" />
                  )}
                </button>
              )}
              <button
                type="button"
                onClick={() => onSelectCheck(row)}
                className="text-left font-mono text-[12px] font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {row.code}
              </button>
            </div>
            {isExpanded && hasExamples && (
              <div className="rounded-control border border-border bg-surface-subtle p-2.5 text-[11px]">
                <div className="font-semibold text-muted">
                  Example rows (up to 5)
                </div>
                <ul className="mt-1 space-y-0.5 tabular-nums text-ink">
                  {row.examples.map((ex) => (
                    <li key={`${row.code}-${ex.row_id}`}>
                      Row #{ex.row_id} · {ex.ticket_id}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      },
    },
    {
      key: "severity",
      header: "Severity",
      render: (row) =>
        row.count > 0 ? (
          <StatusPill variant="warning" label="Warning" />
        ) : (
          <StatusPill variant="success" label="Passed" />
        ),
    },
    {
      key: "count",
      header: "Rows affected",
      numeric: true,
      render: (row) => row.count.toLocaleString(),
    },
    {
      key: "affects",
      header: "Affects",
      render: (row) => (
        <span className="text-[12px] text-muted">
          {formatAffects(row.affects)}
        </span>
      ),
    },
    {
      key: "message",
      header: "Explanation & recommended action",
      render: (row) => (
        <div className="space-y-1 text-[12px]">
          <p className="text-ink">{row.message}</p>
          <p className="text-muted">Action: {row.recommended_action}</p>
        </div>
      ),
    },
  ];

  return (
    <Card
      title="Validation summary"
      description="Deterministic row-level checks. All rows are stored; flagged rows are excluded only from affected metric scopes."
      headerAction={<TypeLabel type="Observed fact" />}
    >
      <div className="space-y-5">
        <div className="rounded-control border border-border bg-surface-subtle p-4 text-[13px] leading-relaxed text-ink">
          <p className="tabular-nums">
            <span className="font-semibold">
              {report.rows_valid_for_all_metrics.toLocaleString()} of{" "}
              {report.record_count.toLocaleString()}
            </span>{" "}
            rows are valid for all metrics. Exclusions by scope:{" "}
            <span className="font-semibold">
              {report.excluded_by_scope.response_metrics.toLocaleString()}
            </span>{" "}
            excluded from response metrics,{" "}
            <span className="font-semibold">
              {report.excluded_by_scope.resolution_metrics.toLocaleString()}
            </span>{" "}
            excluded from resolution metrics, and{" "}
            <span className="font-semibold">
              {report.excluded_by_scope.triage_metrics.toLocaleString()}
            </span>{" "}
            excluded from triage metrics.
          </p>
        </div>

        {report.dataset_warnings.length > 0 && (
          <div className="space-y-2">
            {report.dataset_warnings.map((warn) => (
              <div
                key={warn.code}
                className="flex items-start gap-2 rounded-control border border-warning/30 bg-warning-soft px-3.5 py-2.5 text-[12px] text-ink"
              >
                <StatusPill variant="warning" label={warn.code} />
                <span>{warn.message}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[12px] text-muted">
            Click a check code to inspect all flagged rows, or expand examples
            inline.
          </p>
          <label className="inline-flex items-center gap-2 text-[12px] font-medium text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={showPassedChecks}
              onChange={(event) => onToggleShowPassed(event.target.checked)}
              className="h-4 w-4 rounded-control border-border accent-accent"
            />
            <span>Show passed checks ({passedCount})</span>
          </label>
        </div>

        {visibleChecks.length === 0 ? (
          <div className="rounded-control border border-success/25 bg-success-soft p-4 text-[13px] text-success">
            All validation checks passed with zero issues detected. Enable
            &ldquo;Show passed checks&rdquo; to inspect all {allChecks.length} checks.
          </div>
        ) : (
          <DataTable
            caption="Data-quality validation checks"
            columns={checkColumns}
            data={
              visibleChecks as Array<
                ValidationCheckReport & Record<string, unknown>
              >
            }
            rowKey={(row) => row.code}
          />
        )}
      </div>
    </Card>
  );
}
