import { FileSpreadsheet, Trash2 } from "lucide-react";
import { Button, Card, StatusPill } from "../ui";
import type { DatasetRecord } from "../../lib/api";
import { formatRelativeTime, formatShortDate } from "../../lib/format";

function formatPeriod(start: string | null, end: string | null): string {
  if (!start || !end) {
    return "Unavailable";
  }
  return `${formatShortDate(start)} – ${formatShortDate(end)}`;
}

export interface DatasetOverviewProps {
  datasets: DatasetRecord[];
  selectedDataset: DatasetRecord;
  confirmDelete: boolean;
  deleting: boolean;
  onSelectDataset: (id: number) => void;
  onRequestDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}

export function DatasetOverview({
  datasets,
  selectedDataset,
  confirmDelete,
  deleting,
  onSelectDataset,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: DatasetOverviewProps) {
  const report = selectedDataset.validation_report;

  return (
    <Card
      title="Dataset overview"
      description="Uploaded ticket dataset metadata and active selection."
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          {selectedDataset.is_active && (
            <StatusPill variant="info" label="Active" />
          )}
          {selectedDataset.is_sample && (
            <StatusPill variant="warning" label="Synthetic data" />
          )}
          {confirmDelete ? (
            <>
              <Button
                variant="destructive"
                loading={deleting}
                onClick={onConfirmDelete}
              >
                Confirm delete
              </Button>
              <Button
                variant="secondary"
                disabled={deleting}
                onClick={onCancelDelete}
              >
                Cancel
              </Button>
            </>
          ) : (
            <Button
              variant="tertiary"
              icon={<Trash2 size={15} strokeWidth={1.75} />}
              onClick={onRequestDelete}
            >
              Delete dataset
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-5">
        {datasets.length > 1 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-border pb-4">
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
              Datasets
            </span>
            {datasets.map((ds) => {
              const isSelected = ds.id === selectedDataset.id;
              return (
                <button
                  key={ds.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelectDataset(ds.id)}
                  className={[
                    "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1 text-[12px] transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                    isSelected
                      ? "border-accent bg-accent-soft font-semibold text-ink"
                      : "border-border bg-surface text-muted hover:bg-surface-subtle hover:text-ink",
                  ].join(" ")}
                >
                  <FileSpreadsheet
                    size={14}
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  <span>{ds.filename}</span>
                  {ds.is_active && (
                    <span className="text-[10px] font-semibold text-accent">
                      (Active)
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        <dl className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              File name
            </dt>
            <dd className="truncate font-mono text-[12px] font-semibold text-ink">
              {selectedDataset.filename}
            </dd>
          </div>
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              Uploaded
            </dt>
            <dd className="text-[12px] text-ink tabular-nums">
              {formatRelativeTime(selectedDataset.uploaded_at)}
            </dd>
          </div>
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              Records
            </dt>
            <dd className="text-[13px] font-semibold text-ink tabular-nums">
              {selectedDataset.record_count.toLocaleString()}
            </dd>
          </div>
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              Data period
            </dt>
            <dd className="text-[12px] text-ink tabular-nums">
              {formatPeriod(
                selectedDataset.period_start,
                selectedDataset.period_end
              )}
            </dd>
          </div>
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              Distinct tickets
            </dt>
            <dd className="text-[13px] font-semibold text-ink tabular-nums">
              {(report?.distinct_ticket_ids ?? 0).toLocaleString()}
            </dd>
          </div>
          <div className="space-y-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              Distinct customers
            </dt>
            <dd className="text-[13px] font-semibold text-ink tabular-nums">
              {(report?.distinct_customers ?? 0).toLocaleString()}
            </dd>
          </div>
        </dl>
      </div>
    </Card>
  );
}
