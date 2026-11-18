import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Button,
  Card,
  DataTable,
  Eyebrow,
  type DataTableColumn,
} from "../ui";
import type { MetricResultRecord } from "../../lib/api";
import { CHART_COLORS } from "../../lib/chartColors";

interface ChartPanelProps<T extends Record<string, unknown>> {
  id: string;
  title: string;
  description: string;
  sampleN: number;
  metricColor: string;
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  renderChart: () => ReactNode;
  extraMeta?: ReactNode;
}

function ChartPanel<T extends Record<string, unknown>>({
  id,
  title,
  description,
  sampleN,
  metricColor,
  columns,
  rows,
  rowKey,
  renderChart,
  extraMeta,
}: ChartPanelProps<T>) {
  const [asTable, setAsTable] = useState(false);

  return (
    <Card
      title={title}
      description={description}
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          <span
            data-metric-color={metricColor}
            className="rounded-control border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-medium text-muted tabular-nums"
          >
            n = {sampleN.toLocaleString()}
          </span>
          <Button
            variant="secondary"
            aria-pressed={asTable}
            onClick={() => setAsTable((prev) => !prev)}
          >
            {asTable ? "View as chart" : "View as table"}
          </Button>
        </div>
      }
    >
      <div
        role="region"
        aria-label={title}
        data-chart-id={id}
        data-metric-color={metricColor}
        className="space-y-3"
      >
        {extraMeta}
        {asTable ? (
          <DataTable
            caption={title}
            columns={columns}
            data={rows}
            rowKey={rowKey}
          />
        ) : (
          <div className="h-64 w-full min-w-0">{renderChart()}</div>
        )}
      </div>
    </Card>
  );
}

interface HourRow extends Record<string, unknown> {
  hour: number;
  count: number;
  share: number;
}

interface DayRow extends Record<string, unknown> {
  date: string;
  count: number;
  share: number;
}

interface BandRow extends Record<string, unknown> {
  band: string;
  hours: string;
  n: number;
  median: number | null;
  p90: number | null;
  mean: number | null;
}

interface BacklogBucketRow extends Record<string, unknown> {
  bucket: string;
  min_days: number;
  max_days: number | null;
  count: number;
  share: number;
}

interface AgentRow extends Record<string, unknown> {
  agent: string;
  count: number;
  share: number;
}

interface ReassignCategoryRow extends Record<string, unknown> {
  category: string;
  n: number;
  reassigned_count: number;
  rate: number;
  mean_reassignments: number;
}

interface CategoryDelayRow extends Record<string, unknown> {
  category: string;
  n: number;
  median_triage_hours: number | null;
  median_first_response_hours: number | null;
  median_resolution_hours: number | null;
  reassignment_rate: number | null;
}

export interface DiagnosticsChartsProps {
  metrics: Record<string, MetricResultRecord>;
}

export function DiagnosticsCharts({ metrics }: DiagnosticsChartsProps) {
  const hourMetric = metrics.volume_by_hour as MetricResultRecord<HourRow[]>;
  const dayMetric = metrics.volume_by_day as MetricResultRecord<DayRow[]>;
  const bandMetric = metrics.first_response_by_band as MetricResultRecord<BandRow[]>;
  const backlogMetric = metrics.backlog_ageing as MetricResultRecord<{
    total_open_backlog: number;
    oldest_age_days: number | null;
    buckets: BacklogBucketRow[];
  }>;
  const workloadMetric = metrics.agent_workload as MetricResultRecord<{
    assigned_total: number;
    unassigned_count: number;
    top_n: number;
    top_n_agents: string[];
    top_n_share: number | null;
    gini: number | null;
    agents: AgentRow[];
  }>;
  const reassignMetric = metrics.reassignment_rate as MetricResultRecord<{
    overall: { n: number; rate: number | null };
    by_category: ReassignCategoryRow[];
  }>;
  const categoryDelayMetric = metrics.category_delay_table as MetricResultRecord<
    CategoryDelayRow[]
  >;

  const hourRows = hourMetric?.data ?? [];
  const dayRows = dayMetric?.data ?? [];
  const bandRows = bandMetric?.data ?? [];
  const backlogBuckets = backlogMetric?.data?.buckets ?? [];
  const agentRows = workloadMetric?.data?.agents ?? [];
  const reassignCategoryRows = (reassignMetric?.data?.by_category ?? []).map(
    (r) => ({
      ...r,
      rate_pct: Number((r.rate * 100).toFixed(2)),
    })
  );
  const categoryDelayRows = categoryDelayMetric?.data ?? [];

  const categoryDelayColumns: DataTableColumn<CategoryDelayRow>[] = [
    { key: "category", header: "Category" },
    { key: "n", header: "Tickets", numeric: true },
    {
      key: "median_triage_hours",
      header: "Median triage (h)",
      numeric: true,
      render: (r) => (r.median_triage_hours ?? "—").toString(),
    },
    {
      key: "median_first_response_hours",
      header: "Median FRT (h)",
      numeric: true,
      render: (r) => (r.median_first_response_hours ?? "—").toString(),
    },
    {
      key: "median_resolution_hours",
      header: "Median resolution (h)",
      numeric: true,
      render: (r) => (r.median_resolution_hours ?? "—").toString(),
    },
    {
      key: "reassignment_rate",
      header: "Reassigned (%)",
      numeric: true,
      render: (r) =>
        r.reassignment_rate !== null
          ? `${(r.reassignment_rate * 100).toFixed(1)}%`
          : "—",
    },
  ];

  return (
    <section id="section-charts" aria-label="Diagnostic charts and tables" className="space-y-6">
      <div className="space-y-1">
        <Eyebrow>Distributions & Breakdowns</Eyebrow>
        <h2 className="text-[20px] font-semibold text-ink">
          Charts and analytical tables
        </h2>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 1. Volume by hour of day */}
        <ChartPanel
          id="volume-by-hour"
          title="Ticket volume by hour of day (IST)"
          description="Ticket creation counts across 00:00–23:00 IST."
          sampleN={hourMetric?.n_included ?? 0}
          metricColor={CHART_COLORS.volume}
          columns={[
            { key: "hour", header: "Hour (IST)", numeric: true },
            { key: "count", header: "Tickets", numeric: true },
            {
              key: "share",
              header: "Share",
              numeric: true,
              render: (r) => `${(r.share * 100).toFixed(1)}%`,
            },
          ]}
          rows={hourRows}
          rowKey={(r) => String(r.hour)}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <BarChart data={hourRows} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="hour"
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Hour (IST)", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Tickets", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Bar dataKey="count" name="Tickets" fill={CHART_COLORS.volume} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        />

        {/* 2. Daily volume */}
        <ChartPanel
          id="volume-by-day"
          title="Daily ticket volume (IST)"
          description="Daily ticket inflow over the dataset period."
          sampleN={dayMetric?.n_included ?? 0}
          metricColor={CHART_COLORS.volume}
          columns={[
            { key: "date", header: "Date (IST)" },
            { key: "count", header: "Tickets", numeric: true },
            {
              key: "share",
              header: "Share",
              numeric: true,
              render: (r) => `${(r.share * 100).toFixed(1)}%`,
            },
          ]}
          rows={dayRows}
          rowKey={(r) => r.date}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <LineChart data={dayRows} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="date"
                  stroke={CHART_COLORS.axis}
                  fontSize={10}
                  minTickGap={24}
                  label={{ value: "Date (IST)", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Tickets", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Tickets"
                  stroke={CHART_COLORS.volume}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        />

        {/* 3. First response by creation band (median + p90) */}
        <ChartPanel
          id="first-response-by-band"
          title="First-response time by creation band (hours)"
          description="Median and p90 first-response time across IST creation-hour bands."
          sampleN={bandMetric?.n_included ?? 0}
          metricColor={CHART_COLORS.first_response}
          columns={[
            { key: "band", header: "Band" },
            { key: "hours", header: "IST Hours" },
            { key: "n", header: "Responded n", numeric: true },
            {
              key: "median",
              header: "Median (h)",
              numeric: true,
              render: (r) => (r.median ?? "—").toString(),
            },
            {
              key: "p90",
              header: "p90 (h)",
              numeric: true,
              render: (r) => (r.p90 ?? "—").toString(),
            },
          ]}
          rows={bandRows}
          rowKey={(r) => r.band}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <BarChart data={bandRows} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="band"
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Creation band", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Hours", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Bar
                  dataKey="median"
                  name="Median (h)"
                  fill={CHART_COLORS.first_response}
                  radius={[3, 3, 0, 0]}
                />
                <Bar
                  dataKey="p90"
                  name="p90 (h)"
                  fill={CHART_COLORS.p90_first_response}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        />

        {/* 4. Backlog ageing */}
        <ChartPanel
          id="backlog-ageing"
          title="Backlog ageing (open & pending tickets)"
          description="Open/pending tickets grouped by age in days at dataset period end."
          sampleN={backlogMetric?.data?.total_open_backlog ?? 0}
          metricColor={CHART_COLORS.backlog}
          extraMeta={
            backlogMetric?.data?.oldest_age_days !== null &&
            backlogMetric?.data?.oldest_age_days !== undefined ? (
              <p className="text-[12px] text-muted tabular-nums">
                Oldest open ticket:{" "}
                <span className="font-semibold text-ink">
                  {backlogMetric.data.oldest_age_days} days
                </span>
              </p>
            ) : null
          }
          columns={[
            { key: "bucket", header: "Age bucket" },
            { key: "count", header: "Tickets", numeric: true },
            {
              key: "share",
              header: "Share",
              numeric: true,
              render: (r) => `${(r.share * 100).toFixed(1)}%`,
            },
          ]}
          rows={backlogBuckets}
          rowKey={(r) => r.bucket}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <BarChart data={backlogBuckets} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="bucket"
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Age bucket (days)", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Tickets", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Bar
                  dataKey="count"
                  name="Tickets"
                  fill={CHART_COLORS.backlog}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        />

        {/* 5. Agent workload */}
        <ChartPanel
          id="agent-workload"
          title="Agent workload distribution"
          description="Assigned tickets per agent with top-3 concentration and Gini coefficient."
          sampleN={workloadMetric?.data?.assigned_total ?? 0}
          metricColor={CHART_COLORS.workload}
          extraMeta={
            <div className="flex flex-wrap gap-4 text-[12px] text-muted tabular-nums">
              <span>
                Top-{workloadMetric?.data?.top_n ?? 3} share:{" "}
                <strong className="text-ink">
                  {workloadMetric?.data?.top_n_share !== null &&
                  workloadMetric?.data?.top_n_share !== undefined
                    ? `${(workloadMetric.data.top_n_share * 100).toFixed(1)}%`
                    : "—"}
                </strong>
              </span>
              <span>
                Gini:{" "}
                <strong className="text-ink">
                  {workloadMetric?.data?.gini !== null &&
                  workloadMetric?.data?.gini !== undefined
                    ? workloadMetric.data.gini.toFixed(2)
                    : "—"}
                </strong>
              </span>
              <span>
                Unassigned:{" "}
                <strong className="text-ink">
                  {(workloadMetric?.data?.unassigned_count ?? 0).toLocaleString()}
                </strong>
              </span>
            </div>
          }
          columns={[
            { key: "agent", header: "Agent" },
            { key: "count", header: "Tickets", numeric: true },
            {
              key: "share",
              header: "Share",
              numeric: true,
              render: (r) => `${(r.share * 100).toFixed(1)}%`,
            },
          ]}
          rows={agentRows}
          rowKey={(r) => r.agent}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <BarChart data={agentRows} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="agent"
                  stroke={CHART_COLORS.axis}
                  fontSize={10}
                  label={{ value: "Agent", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Tickets", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Bar
                  dataKey="count"
                  name="Tickets"
                  fill={CHART_COLORS.workload}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        />

        {/* 6. Reassignment rate by category */}
        <ChartPanel
          id="reassignment-by-category"
          title="Reassignment rate by category (%)"
          description="Share of tickets reassigned at least once per category."
          sampleN={reassignMetric?.data?.overall?.n ?? 0}
          metricColor={CHART_COLORS.reassignment}
          columns={[
            { key: "category", header: "Category" },
            { key: "n", header: "Tickets", numeric: true },
            { key: "reassigned_count", header: "Reassigned", numeric: true },
            {
              key: "rate_pct",
              header: "Rate (%)",
              numeric: true,
              render: (r) => `${r.rate_pct}%`,
            },
          ]}
          rows={reassignCategoryRows}
          rowKey={(r) => r.category}
          renderChart={() => (
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={220}>
              <BarChart
                data={reassignCategoryRows}
                margin={{ top: 8, right: 16, bottom: 20, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis
                  dataKey="category"
                  stroke={CHART_COLORS.axis}
                  fontSize={10}
                  label={{ value: "Category", position: "insideBottom", offset: -10, fontSize: 11 }}
                />
                <YAxis
                  stroke={CHART_COLORS.axis}
                  fontSize={11}
                  label={{ value: "Reassigned (%)", angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Bar
                  dataKey="rate_pct"
                  name="Reassigned (%)"
                  fill={CHART_COLORS.reassignment}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        />
      </div>

      {/* 7. Category delay table */}
      <Card
        title="Category delay table"
        description="Median triage, first-response, and resolution hours plus reassignment rate per category."
        headerAction={
          <span className="rounded-control border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-medium text-muted tabular-nums">
            n = {(categoryDelayMetric?.n_included ?? 0).toLocaleString()}
          </span>
        }
      >
        <DataTable
          caption="Category delay breakdown"
          columns={categoryDelayColumns}
          data={categoryDelayRows}
          rowKey={(r) => r.category}
        />
      </Card>
    </section>
  );
}
