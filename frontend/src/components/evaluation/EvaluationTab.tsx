import { useCallback, useEffect, useState } from "react";
import { Eyebrow, StatusPill, SyntheticDataNotice } from "../ui";
import { RunControls } from "./RunControls";
import { ProgressCard } from "./ProgressCard";
import { ResultsSummary } from "./ResultsSummary";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { SlicesTable } from "./SlicesTable";
import { FailureCasesList } from "./FailureCasesList";
import { RunHistory } from "./RunHistory";
import {
  cancelEvalRun,
  createEvalRun,
  fetchEvalRun,
  fetchEvalRunItems,
  fetchEvalRuns,
  resumeEvalRun,
  type CreateEvalRunPayload,
  type EvalItem,
  type EvalRunSummary,
} from "../../lib/api";

export interface EvaluationTabProps {
  engagementId: number;
  configuredModel?: string;
  llmConfigured?: boolean;
}

export function EvaluationTab({
  engagementId,
  configuredModel = "openai/gpt-oss-20b",
  llmConfigured = true,
}: EvaluationTabProps) {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [activeRun, setActiveRun] = useState<EvalRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Failed items state for FailureCasesList expanded view
  const [failedItems, setFailedItems] = useState<EvalItem[]>([]);
  const [isLoadingFailed, setIsLoadingFailed] = useState<boolean>(false);

  // Load runs
  const loadRuns = useCallback(async () => {
    try {
      const data = await fetchEvalRuns(engagementId);
      setRuns(data);
      if (data.length > 0) {
        // If nothing selected or selected not in list, default to first (newest)
        setSelectedRunId((prev) => {
          if (prev && data.some((r) => r.id === prev)) return prev;
          return data[0].id;
        });
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load evaluation runs");
    }
  }, [engagementId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Load selected run details
  const loadRunDetail = useCallback(async (runId: number) => {
    try {
      const detail = await fetchEvalRun(engagementId, runId);
      setActiveRun(detail);
      // Also update in runs list
      setRuns((prev) => prev.map((r) => (r.id === detail.id ? detail : r)));
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load run details");
    }
  }, [engagementId]);

  useEffect(() => {
    if (selectedRunId) {
      loadRunDetail(selectedRunId);
    } else {
      setActiveRun(null);
    }
  }, [selectedRunId, loadRunDetail]);

  // Polling for active run (running or paused)
  useEffect(() => {
    if (!activeRun || (activeRun.status !== "running" && activeRun.status !== "paused")) {
      return;
    }
    const interval = setInterval(() => {
      loadRunDetail(activeRun.id);
    }, 2000);
    return () => clearInterval(interval);
  }, [activeRun, loadRunDetail]);

  // Handle start run
  const handleStartRun = async (payload: CreateEvalRunPayload) => {
    setErrorMessage(null);
    try {
      const resp = await createEvalRun(engagementId, payload);
      const newRun = await fetchEvalRun(engagementId, resp.run_id);
      setRuns((prev) => [newRun, ...prev]);
      setSelectedRunId(newRun.id);
      setActiveRun(newRun);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to start evaluation run");
    }
  };

  // Handle resume run
  const handleResumeRun = async (runId: number) => {
    setErrorMessage(null);
    try {
      const resumed = await resumeEvalRun(engagementId, runId);
      setActiveRun(resumed);
      setRuns((prev) => prev.map((r) => (r.id === resumed.id ? resumed : r)));
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to resume evaluation run");
    }
  };

  // Handle cancel run
  const handleCancelRun = async (runId: number) => {
    setErrorMessage(null);
    try {
      const cancelled = await cancelEvalRun(engagementId, runId);
      setActiveRun(cancelled);
      setRuns((prev) => prev.map((r) => (r.id === cancelled.id ? cancelled : r)));
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to cancel evaluation run");
    }
  };

  // Load all failed items for active run
  const handleLoadFailedItems = async () => {
    if (!activeRun) return;
    setIsLoadingFailed(true);
    try {
      const resp = await fetchEvalRunItems(engagementId, activeRun.id, {
        failure_only: true,
        page_size: 150,
      });
      setFailedItems(resp.items);
    } catch (err: any) {
      console.error("Failed to load failed items:", err);
    } finally {
      setIsLoadingFailed(false);
    }
  };

  const isAnyRunning = runs.some((r) => r.status === "running");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-3">
        <Eyebrow>TIER-2 BENCHMARK</Eyebrow>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-[32px] font-normal tracking-tight text-ink">
              Agent evaluation
            </h1>
            <p className="text-[14px] text-muted max-w-3xl mt-1">
              Deterministic evaluation of production classification against the 150 labelled eval tickets.
              Test set held out; no prompts or rules may be tuned to eval results.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <StatusPill variant="neutral" label="150 synthetic eval tickets" />
            <StatusPill variant="info" label="Held-out test set" />
            <StatusPill variant="neutral" label="Deterministic priority (R1)" />
          </div>
        </div>
      </div>

      <SyntheticDataNotice />

      {/* Error banner if any */}
      {errorMessage && (
        <div className="rounded-button border border-danger/30 bg-danger-soft p-3 text-[13px] text-danger">
          {errorMessage}
        </div>
      )}

      {/* Run Controls */}
      <RunControls
        onStartRun={handleStartRun}
        isRunning={isAnyRunning}
        configuredModel={configuredModel}
        disabled={!llmConfigured}
      />

      {/* Live region announcing completion */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid="eval-live-announcer"
      >
        {activeRun && activeRun.status === "completed"
          ? `Evaluation run ${activeRun.id} completed. Category accuracy: ${activeRun.results?.summary?.category_accuracy_pct}%.`
          : ""}
      </div>

      {/* Empty state when no runs exist */}
      {runs.length === 0 && !activeRun && (
        <div className="rounded-card border border-border/80 bg-surface p-8 text-center space-y-3">
          <h3 className="font-display text-[18px] text-ink font-normal">
            No evaluations run yet
          </h3>
          <p className="text-[13px] text-muted max-w-xl mx-auto">
            Run an evaluation to test the production triage classifier against 150 held-out synthetic tickets.
            Calculates strict category accuracy with 95% Wilson score interval, deterministic priority conformance,
            and subgroup slices.
          </p>
        </div>
      )}

      {/* Progress card if active run is running or paused */}
      {activeRun && (activeRun.status === "running" || activeRun.status === "paused") && (
        <ProgressCard
          run={activeRun}
          onResume={handleResumeRun}
          onCancel={handleCancelRun}
        />
      )}

      {/* Completed results display */}
      {activeRun && activeRun.status === "completed" && activeRun.results && (
        <div className="space-y-8">
          <ResultsSummary run={activeRun} />
          <ConfusionMatrix results={activeRun.results} />
          <SlicesTable slices={activeRun.results.slices} />
          <FailureCasesList
            failureCases={activeRun.results.failure_cases}
            draftChecks={activeRun.results.draft_checks || (activeRun.results as any).draft_check}
            onViewAllFailed={handleLoadFailedItems}
            failedItems={failedItems}
            isLoadingFailedItems={isLoadingFailed}
          />
        </div>
      )}

      {/* Run History Archive */}
      <RunHistory
        runs={runs}
        selectedRunId={selectedRunId}
        onSelectRun={(id) => setSelectedRunId(id)}
      />
    </div>
  );
}
