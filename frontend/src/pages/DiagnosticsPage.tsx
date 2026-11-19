import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Database,
  Loader2,
} from "lucide-react";
import { AssistantPanel } from "../components/diagnostics/AssistantPanel";
import { DatasetOverview } from "../components/diagnostics/DatasetOverview";
import { DiagnosticsAnalysis } from "../components/diagnostics/DiagnosticsAnalysis";
import { RowDrilldown } from "../components/diagnostics/RowDrilldown";
import {
  UPLOAD_PHASES,
  UploadPanel,
} from "../components/diagnostics/UploadPanel";
import { ValidationSummary } from "../components/diagnostics/ValidationSummary";
import {
  Button,
  Card,
  EmptyState,
  Eyebrow,
  SyntheticDataNotice,
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
  type ValidationCheckReport,
} from "../lib/api";

export function DiagnosticsPage() {
  const {
    activeEngagement,
    loading: engagementsLoading,
    error: engagementsError,
    refreshEngagements,
  } = useEngagement();

  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetsError, setDatasetsError] = useState<string | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPhaseIndex, setUploadPhaseIndex] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [showPassedChecks, setShowPassedChecks] = useState(false);
  const [expandedChecks, setExpandedChecks] = useState<Record<string, boolean>>({});
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [drilldownCheck, setDrilldownCheck] =
    useState<ValidationCheckReport | null>(null);
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

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <Eyebrow>Stage 02 · Diagnose</Eyebrow>
        <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
          Diagnostics
        </h1>
      </header>

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
          <UploadPanel
            compact={false}
            uploading={uploading}
            uploadPhaseIndex={uploadPhaseIndex}
            selectedFile={selectedFile}
            uploadError={uploadError}
            onUploadFile={(file) => void handleUploadFile(file)}
            onLoadSample={() => void handleSampleLoad()}
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start">
          <div className="min-w-0 flex-1 space-y-6">
            <nav
              aria-label="Diagnostics sections"
              className="flex flex-wrap items-center gap-2 border-b border-border pb-3 text-[12px]"
            >
              {[
                { href: "#section-data", label: "Data" },
                { href: "#section-kpis", label: "KPIs" },
                { href: "#section-charts", label: "Charts" },
                { href: "#section-findings", label: "Findings" },
                { href: "#section-questions", label: "Questions" },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="rounded-control border border-border bg-surface px-3 py-1 font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  {item.label}
                </a>
              ))}
            </nav>

            <div id="section-data" className="space-y-6">
              {selectedDataset.is_sample && <SyntheticDataNotice />}

              <DatasetOverview
                datasets={datasets}
                selectedDataset={selectedDataset}
                confirmDelete={confirmDelete}
                deleting={deleting}
                onSelectDataset={(id) => {
                  setSelectedDatasetId(id);
                  setDrilldownCheck(null);
                  setDrilldownData(null);
                  setConfirmDelete(false);
                }}
                onRequestDelete={() => setConfirmDelete(true)}
                onCancelDelete={() => setConfirmDelete(false)}
                onConfirmDelete={() => void handleConfirmDelete()}
              />

              {selectedDataset.validation_report && (
                <ValidationSummary
                  report={selectedDataset.validation_report}
                  showPassedChecks={showPassedChecks}
                  expandedChecks={expandedChecks}
                  onToggleShowPassed={setShowPassedChecks}
                  onToggleExamples={(code) =>
                    setExpandedChecks((prev) => ({
                      ...prev,
                      [code]: !prev[code],
                    }))
                  }
                  onSelectCheck={(check) => {
                    setDrilldownCheck(check);
                    setDrilldownPage(1);
                    setDrilldownData(null);
                    setDrilldownError(null);
                  }}
                />
              )}

              {drilldownCheck && (
                <RowDrilldown
                  check={drilldownCheck}
                  page={drilldownPage}
                  data={drilldownData}
                  loading={drilldownLoading}
                  error={drilldownError}
                  onClose={() => {
                    setDrilldownCheck(null);
                    setDrilldownData(null);
                    setDrilldownError(null);
                  }}
                  onRetry={() =>
                    void loadDrilldownRows(
                      activeEngagement.id,
                      selectedDataset.id,
                      drilldownCheck.code,
                      drilldownPage
                    )
                  }
                  onPageChange={setDrilldownPage}
                />
              )}
            </div>

            <DiagnosticsAnalysis
              engagementId={activeEngagement.id}
              datasetId={selectedDataset.id}
            />

            <Card
              title="Upload new dataset"
              description="Upload another CSV export or reload the synthetic sample dataset."
              headerAction={
                <Database
                  size={16}
                  strokeWidth={1.75}
                  className="text-muted"
                  aria-hidden="true"
                />
              }
            >
              <UploadPanel
                compact={true}
                uploading={uploading}
                uploadPhaseIndex={uploadPhaseIndex}
                selectedFile={selectedFile}
                uploadError={uploadError}
                onUploadFile={(file) => void handleUploadFile(file)}
                onLoadSample={() => void handleSampleLoad()}
              />
            </Card>
          </div>

          <AssistantPanel
            engagementId={activeEngagement.id}
            datasetId={selectedDataset.id}
          />
        </div>
      )}
    </div>
  );
}
