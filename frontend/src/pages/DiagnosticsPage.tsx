import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  FileSpreadsheet,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  Eyebrow,
  StatusPill,
  SyntheticDataNotice,
  TypeLabel,
  type DataTableColumn,
} from "../components/ui";
import { useEngagement } from "../context/EngagementContext";
import {
  deleteDataset,
  fetchDatasetRows,
  fetchDatasets,
  loadSampleDataset,
  uploadDatasetFile,
  type DatasetRecord,
  type DatasetRowsPage,
  type TicketRowRecord,
  type ValidationCheckReport,
} from "../lib/api";
import { formatRelativeTime, formatShortDate } from "../lib/format";

type UploadPhase = "Uploading" | "Validating" | "Saving";

const UPLOAD_PHASES: UploadPhase[] = ["Uploading", "Validating", "Saving"];

const REQUIRED_COLUMNS_LIST = [
  "ticket_id",
  "created_at",
  "assigned_at",
  "first_response_at",
  "resolved_at",
  "category",
  "priority",
  "queue",
  "assigned_agent",
  "status",
  "channel",
  "reassignment_count",
  "customer_id",
];

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

function formatPeriod(start: string | null, end: string | null): string {
  if (!start || !end) {
    return "Unavailable";
  }
  return `${formatShortDate(start)} – ${formatShortDate(end)}`;
}

export function DiagnosticsPage() {
  const {
    activeEngagement,
    loading: engagementsLoading,
    error: engagementsError,
    refreshEngagements,
  } = useEngagement();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetsError, setDatasetsError] = useState<string | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);

  // Upload & sample loading state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPhaseIndex, setUploadPhaseIndex] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showRequiredColumns, setShowRequiredColumns] = useState(false);

  // Validation table state
  const [showPassedChecks, setShowPassedChecks] = useState(false);
  const [expandedChecks, setExpandedChecks] = useState<Record<string, boolean>>({});

  // Delete confirmation state
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Row drill-down state
  const [drilldownCheck, setDrilldownCheck] = useState<ValidationCheckReport | null>(null);
  const [drilldownPage, setDrilldownPage] = useState(1);
  const [drilldownData, setDrilldownData] = useState<DatasetRowsPage | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);

  const loadDatasetsForEngagement = useCallback(
    async (engagementId: number, signal?: AbortSignal) => {
      setDatasetsLoading(true);
      setDatasetsError(null);
      try {
        const items = await fetchDatasets(engagementId, signal);
        setDatasets(items);
        setSelectedDatasetId((current) => {
          if (current !== null && items.some((d) => d.id === current)) {
            return current;
          }
          const active = items.find((d) => d.is_active) ?? items[0];
          return active ? active.id : null;
        });
      } catch (err) {
        if (!signal?.aborted) {
          setDatasetsError(
            err instanceof Error ? err.message : "Unable to load datasets."
          );
        }
      } finally {
        if (!signal?.aborted) {
          setDatasetsLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    if (!activeEngagement) {
      setDatasets([]);
      setSelectedDatasetId(null);
      setDrilldownCheck(null);
      setDrilldownData(null);
      return;
    }

    const controller = new AbortController();
    setDrilldownCheck(null);
    setDrilldownData(null);
    setConfirmDelete(false);
    setExpandedChecks({});
    void loadDatasetsForEngagement(activeEngagement.id, controller.signal);
    return () => controller.abort();
  }, [activeEngagement, loadDatasetsForEngagement]);

  // Cycle visual upload phase while an upload or sample load is in flight.
  useEffect(() => {
    if (!uploading) {
      setUploadPhaseIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setUploadPhaseIndex((prev) =>
        prev < UPLOAD_PHASES.length - 1 ? prev + 1 : prev
      );
    }, 350);
    return () => window.clearInterval(timer);
  }, [uploading]);

  const selectedDataset = useMemo(
    () => datasets.find((d) => d.id === selectedDatasetId) ?? datasets[0] ?? null,
    [datasets, selectedDatasetId]
  );

  const loadDrilldownRows = useCallback(
    async (
      engagementId: number,
      datasetId: number,
      flagCode: string,
      page: number,
      signal?: AbortSignal
    ) => {
      setDrilldownLoading(true);
      setDrilldownError(null);
      try {
        const result = await fetchDatasetRows(
          engagementId,
          datasetId,
          { flag: flagCode, page, pageSize: 25 },
          signal
        );
        setDrilldownData(result);
      } catch (err) {
        if (!signal?.aborted) {
          setDrilldownError(
            err instanceof Error
              ? err.message
              : "Unable to load flagged ticket rows."
          );
        }
      } finally {
        if (!signal?.aborted) {
          setDrilldownLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    if (!activeEngagement || !selectedDataset || !drilldownCheck) {
      return;
    }
    const controller = new AbortController();
    void loadDrilldownRows(
      activeEngagement.id,
      selectedDataset.id,
      drilldownCheck.code,
      drilldownPage,
      controller.signal
    );
    return () => controller.abort();
  }, [
    activeEngagement,
    selectedDataset,
    drilldownCheck,
    drilldownPage,
    loadDrilldownRows,
  ]);

  const handleUploadFile = async (file: File) => {
    if (!activeEngagement) {
      return;
    }
    setSelectedFile(file);
    setUploadError(null);
    setStatusMessage(null);
    setUploading(true);
    setUploadPhaseIndex(0);

    try {
      const created = await uploadDatasetFile(activeEngagement.id, file);
      setDatasets((prev) => [
        created,
        ...prev.map((item) => ({ ...item, is_active: false })),
      ]);
      setSelectedDatasetId(created.id);
      setDrilldownCheck(null);
      setDrilldownData(null);
      setExpandedChecks({});
      setConfirmDelete(false);
      setStatusMessage(
        `Uploaded "${created.filename}" (${created.record_count.toLocaleString()} rows validated).`
      );
    } catch (err) {
      setUploadError(
        err instanceof Error && err.message
          ? err.message
          : "Upload failed. Check the file format and try again."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleSampleLoad = async () => {
    if (!activeEngagement) {
      return;
    }
    setSelectedFile(null);
    setUploadError(null);
    setStatusMessage(null);
    setUploading(true);
    setUploadPhaseIndex(0);

    try {
      const created = await loadSampleDataset(activeEngagement.id);
      setDatasets((prev) => [
        created,
        ...prev.map((item) => ({ ...item, is_active: false })),
      ]);
      setSelectedDatasetId(created.id);
      setDrilldownCheck(null);
      setDrilldownData(null);
      setExpandedChecks({});
      setConfirmDelete(false);
      setStatusMessage(
        `Loaded synthetic sample "${created.filename}" (${created.record_count.toLocaleString()} rows validated).`
      );
    } catch (err) {
      setUploadError(
        err instanceof Error && err.message
          ? err.message
          : "Unable to load the sample dataset."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      void handleUploadFile(file);
    }
    event.target.value = "";
  };

  const openFileChooser = () => {
    fileInputRef.current?.click();
  };

  const handleDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openFileChooser();
    }
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = () => {
    setDragActive(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      void handleUploadFile(file);
    }
  };

  const handleConfirmDelete = async () => {
    if (!activeEngagement || !selectedDataset) {
      return;
    }
    setDeleting(true);
    setUploadError(null);
    setStatusMessage(null);
    try {
      const deletedName = selectedDataset.filename;
      const deletedId = selectedDataset.id;
      await deleteDataset(activeEngagement.id, deletedId);
      setConfirmDelete(false);
      setDrilldownCheck(null);
      setDrilldownData(null);
      setDatasets((prev) => {
        const remaining = prev
          .filter((item) => item.id !== deletedId)
          .map((item, idx) => ({ ...item, is_active: idx === 0 }));
        setSelectedDatasetId(remaining[0]?.id ?? null);
        return remaining;
      });
      setStatusMessage(`Deleted dataset "${deletedName}".`);
    } catch (err) {
      setUploadError(
        err instanceof Error && err.message
          ? err.message
          : "Unable to delete dataset."
      );
    } finally {
      setDeleting(false);
    }
  };

  const toggleCheckExamples = (code: string) => {
    setExpandedChecks((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  const openCheckDrilldown = (check: ValidationCheckReport) => {
    setDrilldownCheck(check);
    setDrilldownPage(1);
    setDrilldownData(null);
    setDrilldownError(null);
  };

  if (engagementsLoading) {
    return (
      <div
        role="status"
        aria-busy="true"
        className="flex items-center gap-2 rounded-card border border-border bg-surface p-6 text-[13px] text-muted"
      >
        <Loader2
          size={16}
          strokeWidth={1.75}
          aria-hidden="true"
          className="animate-spin text-accent"
        />
        <span>Loading engagement context...</span>
      </div>
    );
  }

  if (engagementsError) {
    return (
      <div
        role="alert"
        className="rounded-card border border-danger/30 bg-danger-soft p-6"
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="mt-0.5 shrink-0 text-danger"
          />
          <div className="space-y-2">
            <h2 className="text-[14px] font-semibold text-danger">
              Unable to load Diagnostics
            </h2>
            <p className="text-[13px] text-ink">{engagementsError}</p>
            <Button
              variant="secondary"
              onClick={() => void refreshEngagements()}
            >
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!activeEngagement) {
    return (
      <div className="space-y-6">
        <header className="space-y-1.5">
          <Eyebrow>Stage 02 · Diagnose</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Diagnostics
          </h1>
        </header>

        <EmptyState
          eyebrow="Synthetic workspace"
          title="No engagement selected"
          description="Select or create an engagement in Workspace before uploading and validating a support-ticket CSV dataset."
          icon={<Activity size={16} strokeWidth={1.75} aria-hidden="true" />}
          action={
            <Link
              to="/engagements"
              className="inline-flex h-9 items-center gap-2 rounded-control border border-ink bg-ink px-3.5 text-[13px] font-medium text-surface hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              <span>Go to Engagements</span>
              <ArrowRight size={15} strokeWidth={1.75} aria-hidden="true" />
            </Link>
          }
        />
      </div>
    );
  }

  const report = selectedDataset?.validation_report ?? null;
  const allChecks = report?.checks ?? [];
  const visibleChecks = showPassedChecks
    ? allChecks
    : allChecks.filter((check) => check.count > 0);
  const passedCount = allChecks.filter((check) => check.count === 0).length;

  const checkColumns: DataTableColumn<ValidationCheckReport & Record<string, unknown>>[] = [
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
                  onClick={() => toggleCheckExamples(row.code)}
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
                onClick={() => openCheckDrilldown(row)}
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

  const drilldownColumns: DataTableColumn<TicketRowRecord & Record<string, unknown>>[] = [
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

  const renderUploadControls = (compact: boolean) => (
    <div className="space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        aria-label="CSV file input"
        onChange={handleFileInputChange}
        className="sr-only"
        tabIndex={-1}
      />

      <div
        role="button"
        tabIndex={0}
        aria-label="Upload support ticket CSV file"
        onClick={openFileChooser}
        onKeyDown={handleDropzoneKeyDown}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          "flex flex-col items-start gap-3 rounded-card border border-dashed bg-surface p-6 transition-colors cursor-pointer",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          dragActive ? "border-accent bg-accent-soft/50" : "border-border hover:bg-surface-subtle",
        ].join(" ")}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-surface-subtle text-accent">
            <Upload size={16} strokeWidth={1.75} aria-hidden="true" />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-ink">
              {compact
                ? "Upload another support-ticket CSV"
                : "Drop a support-ticket CSV here, or press Enter / click to choose a file"}
            </div>
            <div className="mt-0.5 text-[12px] text-muted tabular-nums">
              Accepted format: .csv (UTF-8 / UTF-8 BOM) · Max 10 MB · Max 50,000 rows
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Button
            variant="primary"
            disabled={uploading}
            onClick={(event) => {
              event.stopPropagation();
              openFileChooser();
            }}
          >
            Choose CSV file
          </Button>
          <Button
            variant="secondary"
            disabled={uploading}
            onClick={(event) => {
              event.stopPropagation();
              void handleSampleLoad();
            }}
          >
            Load sample dataset
          </Button>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setShowRequiredColumns((prev) => !prev);
            }}
            className="text-[12px] font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            {showRequiredColumns
              ? "Hide required columns"
              : "View 13 required columns (data dictionary)"}
          </button>
        </div>

        {showRequiredColumns && (
          <div
            onClick={(event) => event.stopPropagation()}
            className="w-full rounded-control border border-border bg-surface-subtle p-3 text-[12px]"
          >
            <div className="font-semibold text-ink">
              Required CSV columns (see docs/data-dictionary.md)
            </div>
            <p className="mt-1 font-mono text-[11px] leading-relaxed text-muted">
              {REQUIRED_COLUMNS_LIST.join(", ")}
            </p>
          </div>
        )}
      </div>

      {!compact && (
        <SyntheticDataNotice message="Loading the sample dataset ingests the fictional Kora Living synthetic ticket export (data/sample_tickets.csv) through the same validation pipeline." />
      )}

      {/* Upload progress live region */}
      {uploading && (
        <div
          role="status"
          aria-live="polite"
          aria-busy="true"
          className="space-y-2.5 rounded-card border border-accent/30 bg-accent-soft/60 p-4"
        >
          <div className="flex items-center justify-between gap-3 text-[12px]">
            <div className="flex items-center gap-2 font-semibold text-ink">
              <Loader2
                size={15}
                strokeWidth={1.75}
                aria-hidden="true"
                className="animate-spin text-accent"
              />
              <span>
                {UPLOAD_PHASES[uploadPhaseIndex]}
                {selectedFile ? ` "${selectedFile.name}"...` : " sample dataset..."}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted">
              {UPLOAD_PHASES.map((phase, index) => (
                <span
                  key={phase}
                  className={
                    index === uploadPhaseIndex
                      ? "font-semibold text-accent"
                      : index < uploadPhaseIndex
                        ? "text-ink"
                        : "text-muted"
                  }
                >
                  {phase}
                </span>
              ))}
            </div>
          </div>
          <div
            role="progressbar"
            aria-label="Dataset upload progress"
            aria-busy="true"
            className="h-1.5 w-full overflow-hidden rounded-pill bg-border"
          >
            <div className="h-full w-1/2 animate-pulse rounded-pill bg-accent" />
          </div>
        </div>
      )}

      {/* Upload error keeping selected file name + retry */}
      {uploadError && !uploading && (
        <div
          role="alert"
          className="flex flex-wrap items-start justify-between gap-3 rounded-card border border-danger/30 bg-danger-soft p-4"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle
              size={16}
              strokeWidth={1.75}
              aria-hidden="true"
              className="mt-0.5 shrink-0 text-danger"
            />
            <div className="space-y-1 text-[12px]">
              <div className="font-semibold text-danger">
                Upload failed
                {selectedFile ? ` (${selectedFile.name})` : ""}
              </div>
              <p className="text-ink">{uploadError}</p>
            </div>
          </div>
          {selectedFile && (
            <Button
              variant="secondary"
              onClick={() => void handleUploadFile(selectedFile)}
            >
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );

  const totalDrilldownPages = drilldownData
    ? Math.max(1, Math.ceil(drilldownData.total / drilldownData.page_size))
    : 1;

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <Eyebrow>Stage 02 · Diagnose</Eyebrow>
        <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
          Diagnostics
        </h1>
      </header>

      {/* Success banner rendered ONLY after API confirms success */}
      {statusMessage && !uploading && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-card border border-success/25 bg-success-soft px-4 py-3 text-[13px] font-medium text-success"
        >
          <CheckCircle2 size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{statusMessage}</span>
        </div>
      )}

      {datasetsLoading ? (
        <div
          role="status"
          aria-busy="true"
          className="flex items-center gap-2 rounded-card border border-border bg-surface p-6 text-[13px] text-muted"
        >
          <Loader2
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="animate-spin text-accent"
          />
          <span>Loading uploaded datasets...</span>
        </div>
      ) : datasetsError ? (
        <div
          role="alert"
          className="rounded-card border border-danger/30 bg-danger-soft p-5"
        >
          <div className="flex items-start gap-3">
            <AlertCircle
              size={16}
              strokeWidth={1.75}
              aria-hidden="true"
              className="mt-0.5 shrink-0 text-danger"
            />
            <div className="space-y-2">
              <p className="text-[13px] font-semibold text-danger">
                Unable to load datasets
              </p>
              <p className="text-[12px] text-ink">{datasetsError}</p>
              <Button
                variant="secondary"
                onClick={() =>
                  void loadDatasetsForEngagement(activeEngagement.id)
                }
              >
                Retry
              </Button>
            </div>
          </div>
        </div>
      ) : !selectedDataset ? (
        <Card
          title="Upload operational ticket data"
          description="Validate schema, timestamp consistency, and row-level data quality before running diagnostics. Invalid rows are flagged and retained — never silently dropped."
        >
          {renderUploadControls(false)}
        </Card>
      ) : (
        <div className="space-y-6">
          {selectedDataset.is_sample && <SyntheticDataNotice />}

          {/* Dataset overview & switcher */}
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
                      onClick={() => void handleConfirmDelete()}
                    >
                      Confirm delete
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={deleting}
                      onClick={() => setConfirmDelete(false)}
                    >
                      Cancel
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="tertiary"
                    icon={<Trash2 size={15} strokeWidth={1.75} />}
                    onClick={() => setConfirmDelete(true)}
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
                        onClick={() => {
                          setSelectedDatasetId(ds.id);
                          setDrilldownCheck(null);
                          setDrilldownData(null);
                          setConfirmDelete(false);
                        }}
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

          {/* Validation summary */}
          {report && (
            <Card
              title="Validation summary"
              description="Deterministic row-level checks. All rows are stored; flagged rows are excluded only from affected metric scopes."
              headerAction={<TypeLabel type="Observed fact" />}
            >
              <div className="space-y-5">
                {/* Rows-usable plain-language statement */}
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

                {/* Dataset-level warnings */}
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

                {/* Passed-checks toggle */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[12px] text-muted">
                    Click a check code to inspect all flagged rows, or expand
                    examples inline.
                  </p>
                  <label className="inline-flex items-center gap-2 text-[12px] font-medium text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showPassedChecks}
                      onChange={(event) =>
                        setShowPassedChecks(event.target.checked)
                      }
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
          )}

          {/* Row drill-down */}
          {drilldownCheck && (
            <Card
              title={`Flagged rows: ${drilldownCheck.code}`}
              description={drilldownCheck.message}
              headerAction={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setDrilldownCheck(null);
                    setDrilldownData(null);
                    setDrilldownError(null);
                  }}
                >
                  Close drill-down
                </Button>
              }
            >
              <div className="space-y-4">
                <DataTable
                  caption={`Ticket rows flagged with ${drilldownCheck.code}`}
                  columns={drilldownColumns}
                  data={
                    (drilldownData?.items ?? []) as Array<
                      TicketRowRecord & Record<string, unknown>
                    >
                  }
                  rowKey={(row) => String(row.row_id)}
                  loading={drilldownLoading}
                  error={drilldownError}
                  emptyTitle="No flagged rows found"
                  emptyDescription={`No stored rows carry the ${drilldownCheck.code} flag in this dataset.`}
                  onRetry={() =>
                    void loadDrilldownRows(
                      activeEngagement.id,
                      selectedDataset.id,
                      drilldownCheck.code,
                      drilldownPage
                    )
                  }
                />

                {drilldownData && drilldownData.total > 0 && (
                  <div className="flex items-center justify-between gap-3 text-[12px] text-muted tabular-nums">
                    <span>
                      Showing page {drilldownData.page} of {totalDrilldownPages}{" "}
                      ({drilldownData.total.toLocaleString()} flagged rows)
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        disabled={drilldownPage <= 1 || drilldownLoading}
                        onClick={() =>
                          setDrilldownPage((p) => Math.max(1, p - 1))
                        }
                      >
                        Previous
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={
                          drilldownPage >= totalDrilldownPages ||
                          drilldownLoading
                        }
                        onClick={() => setDrilldownPage((p) => p + 1)}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Secondary upload panel */}
          <Card
            title="Upload new dataset"
            description="Upload another CSV export or reload the synthetic sample dataset."
            headerAction={
              <Database size={16} strokeWidth={1.75} className="text-muted" aria-hidden="true" />
            }
          >
            {renderUploadControls(true)}
          </Card>
        </div>
      )}
    </div>
  );
}
