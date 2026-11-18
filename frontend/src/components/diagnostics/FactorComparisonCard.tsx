import { Card, DataTable, TypeLabel, type DataTableColumn } from "../ui";
import type { MetricResultRecord } from "../../lib/api";

interface FactorRow extends Record<string, unknown> {
  factor_id: string;
  factor: string;
  group_a_label: string;
  group_a_median_hours: number | null;
  group_a_n: number;
  group_b_label: string;
  group_b_median_hours: number | null;
  group_b_n: number;
  difference_hours: number | null;
  note: string;
}

export interface FactorComparisonCardProps {
  metric: MetricResultRecord<FactorRow[]>;
}

export function FactorComparisonCard({ metric }: FactorComparisonCardProps) {
  const rows = metric?.data ?? [];

  const columns: DataTableColumn<FactorRow>[] = [
    {
      key: "factor",
      header: "Factor",
      render: (r) => (
        <div className="space-y-1">
          <div className="font-semibold text-ink">{r.factor}</div>
          <p className="text-[11px] text-muted">{r.note}</p>
        </div>
      ),
    },
    {
      key: "group_a_median_hours",
      header: "Group A median (h)",
      numeric: true,
      render: (r) => (
        <div className="text-right tabular-nums">
          <div className="font-semibold text-ink">
            {r.group_a_median_hours !== null ? `${r.group_a_median_hours} h` : "—"}
          </div>
          <div className="text-[11px] text-muted">
            {r.group_a_label} (n={r.group_a_n.toLocaleString()})
          </div>
        </div>
      ),
    },
    {
      key: "group_b_median_hours",
      header: "Group B median (h)",
      numeric: true,
      render: (r) => (
        <div className="text-right tabular-nums">
          <div className="font-semibold text-ink">
            {r.group_b_median_hours !== null ? `${r.group_b_median_hours} h` : "—"}
          </div>
          <div className="text-[11px] text-muted">
            {r.group_b_label} (n={r.group_b_n.toLocaleString()})
          </div>
        </div>
      ),
    },
    {
      key: "difference_hours",
      header: "Difference (h)",
      numeric: true,
      render: (r) =>
        r.difference_hours !== null ? `${r.difference_hours} h` : "—",
    },
  ];

  return (
    <Card
      title="Factor comparison"
      description="Observed association, not a cause. Side-by-side group medians overlap and are not additive."
      headerAction={<TypeLabel type="Observed fact" />}
    >
      <DataTable
        caption="Observed association, not a cause"
        columns={columns}
        data={rows}
        rowKey={(r) => r.factor_id}
      />
    </Card>
  );
}
