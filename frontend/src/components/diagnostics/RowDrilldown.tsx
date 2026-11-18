import {
  Button,
  Card,
  DataTable,
  StatusPill,
  type DataTableColumn,
} from "../ui";
import type {
  DatasetRowsPage,
  TicketRowRecord,
  ValidationCheckReport,
} from "../../lib/api";
import { formatShortDate } from "../../lib/format";

export interface RowDrilldownProps {
  check: ValidationCheckReport;
  page: number;
  data: DatasetRowsPage | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRetry: () => void;
  onPageChange: (nextPage: number) => void;
}

export function RowDrilldown({
  check,
  page,
  data,
  loading,
  error,
  onClose,
  onRetry,
  onPageChange,
}: RowDrilldownProps) {
  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / data.page_size))
    : 1;

  const drilldownColumns: DataTableColumn<
    TicketRowRecord & Record<string, unknown>
  >[] = [
    {
      key: "ticket_id",
      header: "Ticket ID",
      render: (row) => (
        <span className="font-mono text-[12px] text-ink">{row.ticket_id}</span>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (row) => (
        <span className="tabular-nums text-[12px] text-muted">
          {row.created_at ? formatShortDate(row.created_at) : "Missing"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <span>{row.status ?? "—"}</span>,
    },
    {
      key: "category",
      header: "Category",
      render: (row) => <span>{row.category ?? "—"}</span>,
    },
    {
      key: "validation_flags",
      header: "Flags",
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {row.validation_flags.length === 0 ? (
            <span className="text-[12px] text-muted">None</span>
          ) : (
            row.validation_flags.map((f) => (
              <StatusPill key={f.code} variant="warning" label={f.code} />
            ))
          )}
        </div>
      ),
    },
  ];

  return (
    <Card
      title={`Flagged rows: ${check.code}`}
      description={check.message}
      headerAction={
        <Button variant="secondary" onClick={onClose}>
          Close drill-down
        </Button>
      }
    >
      <div className="space-y-4">
        <DataTable
          caption={`Ticket rows flagged with ${check.code}`}
          columns={drilldownColumns}
          data={
            (data?.items ?? []) as Array<
              TicketRowRecord & Record<string, unknown>
            >
          }
          rowKey={(row) => String(row.row_id)}
          loading={loading}
          error={error}
          emptyTitle="No flagged rows found"
          emptyDescription={`No stored rows carry the ${check.code} flag in this dataset.`}
          onRetry={onRetry}
        />

        {data && data.total > 0 && (
          <div className="flex items-center justify-between gap-3 text-[12px] text-muted tabular-nums">
            <span>
              Showing page {data.page} of {totalPages} (
              {data.total.toLocaleString()} flagged rows)
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                disabled={page <= 1 || loading}
                onClick={() => onPageChange(Math.max(1, page - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page >= totalPages || loading}
                onClick={() => onPageChange(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
