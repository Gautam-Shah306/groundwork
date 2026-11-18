import type { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  numeric?: boolean;
  align?: "left" | "right";
  render?: (row: T) => ReactNode;
}

export interface DataTableProps<T extends Record<string, unknown>> {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T, index: number) => string;
  loading?: boolean;
  error?: string | null;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  caption?: string;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  rowKey,
  loading = false,
  error = null,
  emptyTitle = "No records available",
  emptyDescription = "Data will appear here once operational records are loaded.",
  onRetry,
  caption,
  className = "",
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div
        role="status"
        aria-busy="true"
        className={`rounded-card border border-border bg-surface p-6 ${className}`.trim()}
      >
        <div className="flex items-center gap-2 text-[13px] text-muted">
          <Loader2
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="animate-spin text-accent"
          />
          <span>Loading table data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className={`rounded-card border border-danger/30 bg-danger-soft p-5 ${className}`.trim()}
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="mt-0.5 shrink-0 text-danger"
          />
          <div className="space-y-1">
            <p className="text-[13px] font-semibold text-danger">
              Unable to load table data
            </p>
            <p className="text-[12px] text-ink">{error}</p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-2 inline-flex h-8 items-center rounded-control border border-border bg-surface px-3 text-[12px] font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div
        className={`rounded-card border border-border bg-surface p-6 text-left ${className}`.trim()}
      >
        <p className="text-[13px] font-semibold text-ink">{emptyTitle}</p>
        <p className="mt-1 text-[12px] text-muted">{emptyDescription}</p>
      </div>
    );
  }

  return (
    <div
      className={`overflow-x-auto rounded-card border border-border bg-surface ${className}`.trim()}
    >
      <table className="w-full border-collapse text-left text-[13px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-border bg-surface-subtle">
            {columns.map((column) => {
              const isRight = column.align === "right" || Boolean(column.numeric);
              return (
                <th
                  key={column.key}
                  scope="col"
                  data-numeric={column.numeric ? "true" : undefined}
                  className={[
                    "px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted",
                    isRight ? "text-right tabular-nums" : "text-left",
                  ].join(" ")}
                >
                  {column.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className="border-b border-border last:border-b-0 hover:bg-surface-subtle/70"
            >
              {columns.map((column) => {
                const isRight = column.align === "right" || Boolean(column.numeric);
                const content = column.render
                  ? column.render(row)
                  : (row[column.key] as ReactNode);
                return (
                  <td
                    key={column.key}
                    data-numeric={column.numeric ? "true" : undefined}
                    className={[
                      "px-4 py-3 text-ink",
                      isRight ? "text-right tabular-nums" : "text-left",
                    ].join(" ")}
                  >
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
