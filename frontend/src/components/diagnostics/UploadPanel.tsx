import {
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { AlertCircle, Loader2, Upload } from "lucide-react";
import { Button, SyntheticDataNotice } from "../ui";

export type UploadPhase = "Uploading" | "Validating" | "Saving";

export const UPLOAD_PHASES: UploadPhase[] = [
  "Uploading",
  "Validating",
  "Saving",
];

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

export interface UploadPanelProps {
  compact: boolean;
  uploading: boolean;
  uploadPhaseIndex: number;
  selectedFile: File | null;
  uploadError: string | null;
  onUploadFile: (file: File) => void;
  onLoadSample: () => void;
}

export function UploadPanel({
  compact,
  uploading,
  uploadPhaseIndex,
  selectedFile,
  uploadError,
  onUploadFile,
  onLoadSample,
}: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showRequiredColumns, setShowRequiredColumns] = useState(false);

  const openFileChooser = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onUploadFile(file);
    }
    event.target.value = "";
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
      onUploadFile(file);
    }
  };

  return (
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
          dragActive
            ? "border-accent bg-accent-soft/50"
            : "border-border hover:bg-surface-subtle",
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
              onLoadSample();
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
              onClick={() => onUploadFile(selectedFile)}
            >
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
