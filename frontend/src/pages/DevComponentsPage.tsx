import { Plus, RefreshCw } from "lucide-react";
import {
  Button,
  Card,
  DataTable,
  EVIDENCE_TYPES,
  EmptyState,
  Eyebrow,
  KpiTile,
  StatusPill,
  SyntheticDataNotice,
  TypeLabel,
  type DataTableColumn,
  type StatusPillVariant,
} from "../components/ui";

interface SampleCategoryRow extends Record<string, unknown> {
  category: string;
  tickets: number;
  medianResponseHours: string;
  reassignmentRate: string;
}

const SAMPLE_COLUMNS: DataTableColumn<SampleCategoryRow>[] = [
  { key: "category", header: "Category" },
  { key: "tickets", header: "Tickets", numeric: true },
  { key: "medianResponseHours", header: "Median FRT (h)", numeric: true },
  { key: "reassignmentRate", header: "Reassigned", numeric: true },
];

const SAMPLE_ROWS: SampleCategoryRow[] = [
  {
    category: "Order tracking",
    tickets: 412,
    medianResponseHours: "6.4",
    reassignmentRate: "18.2%",
  },
  {
    category: "Damaged delivery",
    tickets: 198,
    medianResponseHours: "11.2",
    reassignmentRate: "31.5%",
  },
  {
    category: "Returns & refunds",
    tickets: 264,
    medianResponseHours: "8.1",
    reassignmentRate: "22.0%",
  },
];

const STATUS_VARIANTS: Array<{ variant: StatusPillVariant; label: string }> = [
  { variant: "neutral", label: "In progress" },
  { variant: "info", label: "Awaiting approval" },
  { variant: "success", label: "Completed" },
  { variant: "warning", label: "Needs validation" },
  { variant: "danger", label: "Blocked" },
];

export function DevComponentsPage() {
  return (
    <div className="space-y-8" data-testid="dev-components-gallery">
      <header className="space-y-1.5">
        <Eyebrow>Developer · Component Gallery</Eyebrow>
        <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
          Shared UI Components
        </h1>
        <p className="max-w-2xl text-[13px] text-muted">
          Development-only reference showcasing every shared Groundwork component
          and interactive state. Sample figures below are illustrative synthetic
          placeholders only.
        </p>
      </header>

      <Card
        title="Buttons"
        description="Primary, secondary, tertiary, and destructive variants across default, disabled, and loading states."
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" icon={<Plus size={16} strokeWidth={1.75} />}>
              Primary action
            </Button>
            <Button variant="secondary" icon={<RefreshCw size={16} strokeWidth={1.75} />}>
              Secondary action
            </Button>
            <Button variant="tertiary">Tertiary action</Button>
            <Button variant="destructive">Reject proposal</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" disabled>
              Disabled primary
            </Button>
            <Button variant="secondary" disabled>
              Disabled secondary
            </Button>
            <Button variant="primary" loading>
              Saving decision
            </Button>
            <Button variant="secondary" loading>
              Validating CSV
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card
          title="Status pills"
          description="Semantic pills always pair colour and icon with an explicit text label."
        >
          <div className="flex flex-wrap gap-2">
            {STATUS_VARIANTS.map(({ variant, label }) => (
              <StatusPill key={variant} variant={variant} label={label} />
            ))}
          </div>
        </Card>

        <Card
          title="Evidence & integrity labels"
          description="All seven mandatory Groundwork TypeLabel classifications."
        >
          <div className="flex flex-wrap gap-2">
            {EVIDENCE_TYPES.map((type) => (
              <TypeLabel key={type} type={type} />
            ))}
          </div>
        </Card>
      </div>

      <Card
        title="KPI tiles"
        description="Instrument Serif values with tabular numerals. Targets render only when a source is provided."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <KpiTile
            name="Median first-response time"
            value="7.8"
            unit="hours"
            period="Last 30 days (synthetic)"
            baseline="9.4 hours"
            target={{ value: "4.0 hours", source: "SLA policy v1" }}
            statusLabel="Needs validation"
            statusVariant="warning"
          />
          <KpiTile
            name="Unresolved backlog"
            value={142}
            unit="tickets"
            period="Snapshot (synthetic)"
            baseline="118 tickets"
            statusLabel="Observed"
            statusVariant="info"
          />
          <KpiTile
            name="Reassignment rate (no target source)"
            value="23.4"
            unit="%"
            period="Last 30 days (synthetic)"
            target={{ value: "10.0%", source: "" }}
          />
        </div>
      </Card>

      <Card
        title="Data tables"
        description="Uppercase headers, right-aligned numeric columns with tabular numerals, and loading, empty, and error states."
      >
        <div className="space-y-5">
          <div>
            <Eyebrow className="mb-2">Success state</Eyebrow>
            <DataTable
              caption="Synthetic ticket breakdown by category"
              columns={SAMPLE_COLUMNS}
              data={SAMPLE_ROWS}
              rowKey={(row) => row.category}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div>
              <Eyebrow className="mb-2">Loading state</Eyebrow>
              <DataTable
                columns={SAMPLE_COLUMNS}
                data={[]}
                rowKey={(_, idx) => String(idx)}
                loading
              />
            </div>
            <div>
              <Eyebrow className="mb-2">Empty state</Eyebrow>
              <DataTable
                columns={SAMPLE_COLUMNS}
                data={[]}
                rowKey={(_, idx) => String(idx)}
              />
            </div>
            <div>
              <Eyebrow className="mb-2">Error state</Eyebrow>
              <DataTable
                columns={SAMPLE_COLUMNS}
                data={[]}
                rowKey={(_, idx) => String(idx)}
                error="Could not fetch diagnostic metrics from the API."
                onRetry={() => undefined}
              />
            </div>
          </div>
        </div>
      </Card>

      <Card
        title="Synthetic data notice"
        description="Required banner marking synthetic demonstration engagements and simulated outputs (R7)."
      >
        <SyntheticDataNotice />
      </Card>

      <Card
        title="Empty state & Eyebrow"
        description="Standard placeholder structure for screens awaiting operational data."
      >
        <EmptyState
          eyebrow="Stage 02 · Diagnose"
          title="No dataset uploaded"
          description="Upload a synthetic support-ticket CSV to inspect validation warnings and deterministic metrics."
          action={<Button variant="secondary">Select CSV file</Button>}
        />
      </Card>
    </div>
  );
}
