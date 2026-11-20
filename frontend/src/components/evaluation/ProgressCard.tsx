import { useEffect, useState } from "react";
import { AlertTriangle, Clock, Play, XCircle } from "lucide-react";
import { Button, Card, StatusPill } from "../ui";
import type { EvalRunSummary } from "../../lib/api";

export interface ProgressCardProps {
  run: EvalRunSummary;
  onResume: (runId: number) => Promise<void>;
  onCancel: (runId: number) => Promise<void>;
}

export function ProgressCard({ run, onResume, onCancel }: ProgressCardProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const isPaused = run.status === "paused";
  const isRunning = run.status === "running";

  useEffect(() => {
    if (!isRunning) return;
    const startMs = new Date(run.started_at).getTime();
    const updateElapsed = () => {
      const nowMs = Date.now();
      setElapsedSeconds(Math.max(0, Math.floor((nowMs - startMs) / 1000)));
    };
    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [run.started_at, isRunning]);

  const progressTotal = run.progress_total || run.sample_size || 1;
  const progressDone = run.progress_done || 0;
  const percent = Math.min(100, Math.round((progressDone / progressTotal) * 100));

  // Estimate remaining time
  const remainingSeconds =
    progressDone > 0 && elapsedSeconds > 0
      ? Math.max(0, Math.round((elapsedSeconds / progressDone) * (progressTotal - progressDone)))
      : Math.max(0, (progressTotal - progressDone) * 2);

  const formatSec = (s: number) => {
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return m > 0 ? `${m}m ${rem}s` : `${rem}s`;
  };

  const handleResume = async () => {
    setIsActionLoading(true);
    try {
      await onResume(run.id);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setIsActionLoading(true);
    try {
      await onCancel(run.id);
    } finally {
      setIsActionLoading(false);
    }
  };

  return (
    <Card className="p-6 border-accent/20 bg-accent/[0.02]">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <h3 className="font-semibold text-ink text-[15px]">
              {isPaused ? "Evaluation Paused" : "Evaluation in Progress"}
            </h3>
            <StatusPill
              variant={isPaused ? "warning" : "info"}
              label={isPaused ? "Paused" : "Running"}
            />
          </div>

          <div className="flex items-center gap-4 text-[12px] text-muted">
            <span className="flex items-center gap-1 font-mono">
              <Clock size={13} className="text-muted" />
              Elapsed: {formatSec(elapsedSeconds)}
            </span>
            {isRunning && remainingSeconds > 0 && (
              <span className="font-mono">
                Est. remaining: ~{formatSec(remainingSeconds)}
              </span>
            )}
          </div>
        </div>

        {/* Paused error banner */}
        {isPaused && run.error && (
          <div className="flex items-start gap-3 rounded-button border border-warning/30 bg-warning-soft p-3 text-[13px] text-warning">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1 space-y-1">
              <p className="font-medium">Run interrupted: {run.error.code}</p>
              <p className="text-[12px] opacity-90">{run.error.message}</p>
            </div>
          </div>
        )}

        {/* Progress bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[12px] text-muted">
            <span>
              Progress: {progressDone} of {progressTotal} tickets ({percent}%)
            </span>
            <span className="font-mono text-muted">Pacing 2s</span>
          </div>

          <div className="h-2 w-full overflow-hidden rounded-full bg-border/40">
            <div
              className={[
                "h-full transition-all duration-300",
                isPaused ? "bg-warning" : "bg-accent",
              ].join(" ")}
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2">
          {isPaused && (
            <Button
              variant="secondary"
              onClick={handleResume}
              disabled={isActionLoading}
              className="text-[13px]"
            >
              <Play size={13} className="mr-1 fill-current" />
              Resume
            </Button>
          )}

          <Button
            variant="tertiary"
            onClick={handleCancel}
            disabled={isActionLoading}
            className="text-[13px] text-muted hover:text-ink"
          >
            <XCircle size={14} className="mr-1 text-muted" />
            Cancel run
          </Button>
        </div>
      </div>
    </Card>
  );
}
