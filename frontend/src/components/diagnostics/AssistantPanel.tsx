import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  History,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Button, Eyebrow, StatusPill, TypeLabel } from "../ui";
import { formatRunError } from "../../lib/llmErrors";
import {
  ApiRequestError,
  fetchAssistantRun,
  fetchAssistantRuns,
  fetchHealth,
  startAssistantRun,
  type AssistantBlock,
  type AssistantRun,
  type AssistantToolTraceItem,
  type AssistantWarning,
} from "../../lib/api";

export const STARTER_QUESTIONS: readonly string[] = [
  "Why are customers waiting so long?",
  "Where does the time before first response go?",
  "Which categories get reassigned most?",
  "Is the backlog a concern?",
];

const MAX_QUESTION_CHARS = 1000;
const POLL_INTERVAL_MS = 1000;

export interface AssistantPanelProps {
  engagementId: number;
  datasetId: number;
}

function summarizeArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) {
    return "default parameters";
  }
  return entries.map(([k, v]) => `${k}: ${String(v)}`).join(", ");
}

function extractResultSummary(item: AssistantToolTraceItem): {
  definition: string | null;
  scope: string | null;
  n: number | null;
  nExcluded: number | null;
  exclusions: Record<string, number> | null;
} {
  if (!item.ok || !item.data || Array.isArray(item.data)) {
    return {
      definition: null,
      scope: null,
      n: null,
      nExcluded: null,
      exclusions: null,
    };
  }
  const d = item.data;
  if (typeof d.definition === "string") {
    return {
      definition: d.definition,
      scope: typeof d.scope === "string" ? d.scope : null,
      n: typeof d.n_included === "number" ? d.n_included : null,
      nExcluded: typeof d.n_excluded === "number" ? d.n_excluded : null,
      exclusions:
        d.exclusions && typeof d.exclusions === "object"
          ? (d.exclusions as Record<string, number>)
          : null,
    };
  }
  if (d.scope_summary && typeof d.scope_summary === "object") {
    const ss = d.scope_summary as {
      rows_valid_for_all_metrics?: number;
      excluded_by_scope?: Record<string, number>;
    };
    const isFindings = Array.isArray(d.findings);
    return {
      definition: isFindings
        ? `Rule-based diagnostic findings (${(d.findings as unknown[]).length} findings).`
        : "Dataset summary, six baseline operational KPIs, and scope exclusions.",
      scope: "all_metrics",
      n:
        typeof ss.rows_valid_for_all_metrics === "number"
          ? ss.rows_valid_for_all_metrics
          : null,
      nExcluded:
        typeof ss.excluded_by_scope?.all_metrics === "number"
          ? ss.excluded_by_scope.all_metrics
          : null,
      exclusions: ss.excluded_by_scope ?? null,
    };
  }
  return {
    definition: null,
    scope: null,
    n: null,
    nExcluded: null,
    exclusions: null,
  };
}

function warningBadgeLabel(code: AssistantWarning["code"]): string {
  switch (code) {
    case "ungrounded_number":
      return "Ungrounded figure";
    case "number_only_in_uncited_call":
      return "Uncited evidence";
    case "unsupported_finding":
      return "Unsupported statement";
    case "causal_wording_in_finding":
      return "Causal wording";
  }
}

function formatRunTimestamp(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return parsed.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AssistantPanel({
  engagementId,
  datasetId,
}: AssistantPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState<boolean>(true);
  const [notConfiguredMessage, setNotConfiguredMessage] = useState<string | null>(
    null
  );

  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<{
    code: string | null;
    message: string;
  } | null>(null);

  const [displayedRun, setDisplayedRun] = useState<AssistantRun | null>(null);
  const [pollingRunId, setPollingRunId] = useState<number | null>(null);
  const [history, setHistory] = useState<AssistantRun[]>([]);
  const [expandedCalls, setExpandedCalls] = useState<Record<string, boolean>>({});
  const [announcement, setAnnouncement] = useState("");

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activityItemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPollingRunId(null);
  }, []);

  const loadHistory = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const items = await fetchAssistantRuns(engagementId, 10, signal);
        setHistory(items);
      } catch {
        // Non-blocking history fetch; do not surface as an error banner on initial mount.
      }
    },
    [engagementId]
  );

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const health = await fetchHealth(controller.signal);
        if (!health.llm_configured) {
          setLlmConfigured(false);
          setNotConfiguredMessage(
            "Assistant is not configured. Set LLM_API_KEY and LLM_MODEL in your local .env file and restart the backend to enable investigations."
          );
        } else {
          setLlmConfigured(true);
          setNotConfiguredMessage(null);
        }
      } catch {
        // Leave default if health check is unreachable; POST will still enforce 409.
      }
    })();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    stopPolling();
    setDisplayedRun(null);
    setSubmitError(null);
    setExpandedCalls({});
    setAnnouncement("");
    void loadHistory(controller.signal);
    return () => {
      controller.abort();
      stopPolling();
    };
  }, [engagementId, datasetId, loadHistory, stopPolling]);

  useEffect(() => {
    if (pollingRunId === null) {
      return;
    }

    let cancelled = false;
    const pollOnce = async () => {
      try {
        const latest = await fetchAssistantRun(engagementId, pollingRunId);
        if (cancelled) {
          return;
        }
        setDisplayedRun(latest);
        if (latest.status === "completed") {
          stopPolling();
          setAnnouncement("Investigation completed.");
          void loadHistory();
        } else if (latest.status === "failed") {
          stopPolling();
          const msg = formatRunError(
            latest.error?.code,
            latest.error?.message ?? "Investigation failed."
          );
          setAnnouncement(`Investigation failed: ${msg}`);
          void loadHistory();
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        stopPolling();
        const msg =
          err instanceof Error && err.message
            ? err.message
            : "Lost connection while polling investigation status.";
        setSubmitError({ code: "poll_error", message: msg });
        setAnnouncement(`Investigation failed: ${msg}`);
      }
    };

    pollTimerRef.current = setInterval(() => {
      void pollOnce();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (pollTimerRef.current !== null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [engagementId, pollingRunId, stopPolling, loadHistory]);

  const isRunning =
    submitting || pollingRunId !== null || displayedRun?.status === "running";

  const submitQuestion = useCallback(
    async (rawQuestion: string) => {
      const trimmed = rawQuestion.trim();
      if (!trimmed || !llmConfigured || isRunning) {
        return;
      }

      setSubmitting(true);
      setSubmitError(null);
      setAnnouncement("");
      setExpandedCalls({});

      try {
        const started = await startAssistantRun(engagementId, trimmed, datasetId);
        setDisplayedRun({
          id: started.run_id,
          engagement_id: engagementId,
          dataset_id: datasetId,
          question: trimmed,
          status: "running",
          answer_status: "none",
          answer_blocks: [],
          tool_trace: [],
          warnings: [],
          error: null,
          model: "",
          round_trips: 0,
          started_at: new Date().toISOString(),
          finished_at: null,
          duration_ms: null,
        });
        setPollingRunId(started.run_id);
      } catch (err) {
        if (
          err instanceof ApiRequestError &&
          (err.code === "llm_not_configured" ||
            err.code === "unsupported_provider")
        ) {
          setLlmConfigured(false);
          setNotConfiguredMessage(err.message);
        } else if (err instanceof ApiRequestError) {
          setSubmitError({
            code: err.code,
            message: formatRunError(err.code, err.message),
          });
        } else {
          setSubmitError({
            code: "network_error",
            message:
              err instanceof Error && err.message
                ? err.message
                : "Unable to start investigation. Please retry.",
          });
        }
      } finally {
        setSubmitting(false);
      }
    },
    [datasetId, engagementId, isRunning, llmConfigured]
  );

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submitQuestion(question);
  };

  const handleStarterClick = (promptText: string) => {
    setQuestion(promptText);
    void submitQuestion(promptText);
  };

  const handleOpenHistoryRun = async (run: AssistantRun) => {
    stopPolling();
    setSubmitError(null);
    setExpandedCalls({});
    setQuestion(run.question);
    try {
      const fresh = await fetchAssistantRun(engagementId, run.id);
      setDisplayedRun(fresh);
    } catch {
      setDisplayedRun(run);
    }
  };

  const handleEvidenceChipClick = (callId: string) => {
    setExpandedCalls((prev) => ({ ...prev, [callId]: true }));
    const node = activityItemRefs.current[callId];
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  const traceById = useMemo(() => {
    const map: Record<string, AssistantToolTraceItem> = {};
    for (const item of displayedRun?.tool_trace ?? []) {
      map[item.call_id] = item;
    }
    return map;
  }, [displayedRun]);

  const warningsByBlock = useMemo(() => {
    const map: Record<number, AssistantWarning[]> = {};
    for (const warning of displayedRun?.warnings ?? []) {
      if (!map[warning.block_index]) {
        map[warning.block_index] = [];
      }
      map[warning.block_index].push(warning);
    }
    return map;
  }, [displayedRun]);

  if (collapsed) {
    return (
      <aside
        aria-label="Investigation assistant"
        data-testid="assistant-panel-collapsed"
        className="rounded-card border border-accent/25 bg-surface p-3 xl:w-14 xl:shrink-0"
      >
        <button
          type="button"
          aria-expanded="false"
          aria-label="Expand investigation assistant"
          onClick={() => setCollapsed(false)}
          className="inline-flex w-full items-center justify-center gap-2 rounded-control border border-border bg-accent-soft px-2.5 py-2 text-[12px] font-semibold text-accent hover:bg-accent-soft/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <PanelRightOpen size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className="xl:sr-only">Expand investigation assistant</span>
        </button>
      </aside>
    );
  }

  return (
    <aside
      aria-label="Investigation assistant"
      data-testid="assistant-panel"
      className="flex flex-col rounded-card border border-accent/25 bg-surface shadow-[0_7px_24px_rgba(32,42,53,0.03)] xl:w-[390px] xl:shrink-0"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-border bg-accent-soft/45 px-5 py-4">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-accent">
            <Sparkles size={14} strokeWidth={1.75} aria-hidden="true" />
            <Eyebrow className="text-accent">Diagnostics Assistant</Eyebrow>
          </div>
          <h2 className="text-[15px] font-semibold text-ink">
            Investigation assistant
          </h2>
          <p className="text-[11px] leading-relaxed text-muted">
            AI-generated. Figures come from the deterministic metrics shown as
            evidence.
          </p>
        </div>

        <button
          type="button"
          aria-expanded="true"
          aria-label="Collapse investigation assistant"
          onClick={() => setCollapsed(true)}
          className="rounded-control border border-border bg-surface p-1.5 text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <PanelRightClose size={15} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </div>

      {/* Live completion/failure status region */}
      <div
        role="status"
        aria-live="polite"
        data-testid="assistant-live-region"
        className="sr-only"
      >
        {announcement}
      </div>

      <div className="space-y-5 p-5">
        {/* Not-configured banner */}
        {!llmConfigured && (
          <div
            data-testid="assistant-not-configured"
            className="rounded-control border border-warning/30 bg-warning-soft p-3.5 text-[12px] text-ink space-y-1.5"
          >
            <div className="flex items-center gap-1.5 font-semibold text-warning">
              <AlertTriangle size={14} strokeWidth={1.75} aria-hidden="true" />
              <span>Assistant not configured</span>
            </div>
            <p className="leading-relaxed">
              {notConfiguredMessage ??
                "Set LLM_API_KEY and LLM_MODEL in your local .env file and restart the backend to enable investigations."}
            </p>
          </div>
        )}

        {/* Starter questions */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
            Starter questions
          </div>
          <div className="flex flex-wrap gap-1.5">
            {STARTER_QUESTIONS.map((chip) => (
              <button
                key={chip}
                type="button"
                disabled={!llmConfigured || isRunning}
                onClick={() => handleStarterClick(chip)}
                className="rounded-control border border-border bg-surface-subtle px-2.5 py-1.5 text-left text-[11px] font-medium text-ink transition-colors hover:border-accent/40 hover:bg-accent-soft/50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {/* Question input form */}
        <form onSubmit={handleFormSubmit} className="space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor="assistant-question-input"
              className="text-[11px] font-semibold text-ink"
            >
              Ask about this dataset
            </label>
            <span className="text-[10px] text-muted tabular-nums">
              {question.length} / {MAX_QUESTION_CHARS}
            </span>
          </div>

          <textarea
            id="assistant-question-input"
            rows={3}
            maxLength={MAX_QUESTION_CHARS}
            disabled={!llmConfigured}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question grounded in the loaded operational dataset..."
            className="w-full resize-y rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-muted focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:cursor-not-allowed disabled:bg-surface-subtle disabled:opacity-60"
          />

          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-muted">
              Single-turn · aggregate metrics only
            </span>
            <Button
              type="submit"
              variant="primary"
              disabled={!llmConfigured || isRunning || question.trim().length === 0}
            >
              {isRunning ? "Investigating..." : "Investigate"}
            </Button>
          </div>
        </form>

        {/* Submit / polling error banner */}
        {submitError && (
          <div
            role="alert"
            data-testid="assistant-error"
            className="rounded-control border border-danger/30 bg-danger-soft p-3.5 text-[12px] space-y-2"
          >
            <div className="flex items-start gap-2">
              <AlertCircle
                size={15}
                strokeWidth={1.75}
                aria-hidden="true"
                className="mt-0.5 shrink-0 text-danger"
              />
              <p className="text-ink leading-relaxed">{submitError.message}</p>
            </div>
            {llmConfigured && question.trim().length > 0 && (
              <Button
                variant="secondary"
                onClick={() => void submitQuestion(question)}
                disabled={isRunning}
              >
                <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
                <span>Retry</span>
              </Button>
            )}
          </div>
        )}

        {/* Active or selected run view */}
        {displayedRun && (
          <div className="space-y-5 border-t border-border pt-4">
            {/* Run header */}
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                  Run #{displayedRun.id}
                </span>
                {displayedRun.status === "running" ? (
                  <StatusPill
                    variant="info"
                    label="Running"
                    icon={
                      <Loader2
                        size={12}
                        strokeWidth={1.75}
                        className="animate-spin"
                      />
                    }
                  />
                ) : displayedRun.status === "completed" ? (
                  <StatusPill variant="success" label="Completed" />
                ) : (
                  <StatusPill variant="danger" label="Failed" />
                )}
              </div>
              <p className="text-[12px] font-medium text-ink">
                {displayedRun.question}
              </p>
              {displayedRun.status !== "running" && (
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted tabular-nums">
                  {displayedRun.duration_ms !== null && (
                    <span className="inline-flex items-center gap-1">
                      <Clock size={12} strokeWidth={1.75} aria-hidden="true" />
                      {(displayedRun.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  {displayedRun.model && <span>{displayedRun.model}</span>}
                </div>
              )}
            </div>

            {/* Failed run error */}
            {displayedRun.status === "failed" && displayedRun.error && (
              <div
                role="alert"
                data-testid="assistant-run-error"
                className="rounded-control border border-danger/30 bg-danger-soft p-3.5 text-[12px] space-y-2"
              >
                <div className="flex items-start gap-2">
                  <AlertCircle
                    size={15}
                    strokeWidth={1.75}
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-danger"
                  />
                  <div className="space-y-1">
                    <div className="font-semibold text-danger">
                      Investigation could not complete
                    </div>
                    <p className="text-ink leading-relaxed">
                      {formatRunError(
                        displayedRun.error.code,
                        displayedRun.error.message
                      )}
                    </p>
                  </div>
                </div>
                {llmConfigured && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setQuestion(displayedRun.question);
                      void submitQuestion(displayedRun.question);
                    }}
                    disabled={isRunning}
                  >
                    <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
                    <span>Retry</span>
                  </Button>
                )}
              </div>
            )}

            {/* State 1: Analysis (tool activity) */}
            <section
              aria-label="Investigation activity"
              className="space-y-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                  <Wrench size={12} strokeWidth={1.75} aria-hidden="true" />
                  <span>
                    Analysis activity ({displayedRun.tool_trace.length})
                  </span>
                </div>
              </div>

              {displayedRun.status === "running" &&
                displayedRun.tool_trace.length === 0 && (
                  <div className="flex items-center gap-2 rounded-control border border-border bg-surface-subtle px-3 py-2.5 text-[12px] text-muted">
                    <Loader2
                      size={14}
                      strokeWidth={1.75}
                      aria-hidden="true"
                      className="animate-spin text-accent"
                    />
                    <span>Running analysis tools...</span>
                  </div>
                )}

              {displayedRun.tool_trace.length > 0 && (
                <div className="space-y-2">
                  {displayedRun.tool_trace.map((item) => {
                    const isOpen = Boolean(expandedCalls[item.call_id]);
                    const summary = extractResultSummary(item);
                    const exclusionText =
                      summary.exclusions &&
                      Object.keys(summary.exclusions).length > 0
                        ? Object.entries(summary.exclusions)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(", ")
                        : "none";

                    return (
                      <div
                        key={item.call_id}
                        ref={(el) => {
                          activityItemRefs.current[item.call_id] = el;
                        }}
                        data-testid={`activity-item-${item.call_id}`}
                        className="rounded-control border border-border bg-surface-subtle"
                      >
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          onClick={() =>
                            setExpandedCalls((prev) => ({
                              ...prev,
                              [item.call_id]: !prev[item.call_id],
                            }))
                          }
                          className="flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-[12px] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
                        >
                          <div className="flex items-start gap-1.5 min-w-0">
                            {isOpen ? (
                              <ChevronDown
                                size={14}
                                strokeWidth={1.75}
                                aria-hidden="true"
                                className="mt-0.5 shrink-0 text-muted"
                              />
                            ) : (
                              <ChevronRight
                                size={14}
                                strokeWidth={1.75}
                                aria-hidden="true"
                                className="mt-0.5 shrink-0 text-muted"
                              />
                            )}
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="font-mono text-[10px] font-semibold text-accent">
                                  {item.call_id}
                                </span>
                                <span className="font-semibold text-ink">
                                  {item.tool}
                                </span>
                              </div>
                              <div className="truncate text-[11px] text-muted">
                                {summarizeArgs(item.args)}
                              </div>
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-1.5">
                            <span className="text-[10px] text-muted tabular-nums">
                              {item.duration_ms} ms
                            </span>
                            {item.ok ? (
                              <StatusPill
                                variant="neutral"
                                label="Done"
                                icon={
                                  <CheckCircle2
                                    size={12}
                                    strokeWidth={1.75}
                                    aria-hidden="true"
                                  />
                                }
                              />
                            ) : (
                              <StatusPill variant="danger" label="Failed" />
                            )}
                          </div>
                        </button>

                        {isOpen && (
                          <div
                            data-testid={`activity-detail-${item.call_id}`}
                            className="space-y-1.5 border-t border-border bg-surface px-3 py-2.5 text-[11px] text-ink"
                          >
                            <div>
                              <span className="font-semibold text-muted">
                                Arguments:{" "}
                              </span>
                              <code className="font-mono text-[10px]">
                                {JSON.stringify(item.args)}
                              </code>
                            </div>

                            {!item.ok && item.error ? (
                              <p className="text-danger">
                                {item.error.code}: {item.error.message}
                              </p>
                            ) : (
                              <>
                                {summary.definition && (
                                  <p>
                                    <span className="font-semibold text-muted">
                                      Definition:{" "}
                                    </span>
                                    {summary.definition}
                                  </p>
                                )}
                                {summary.scope && (
                                  <p>
                                    <span className="font-semibold text-muted">
                                      Scope:{" "}
                                    </span>
                                    {summary.scope}
                                  </p>
                                )}
                                {summary.n !== null && (
                                  <p className="tabular-nums">
                                    <span className="font-semibold text-muted">
                                      Sample (n):{" "}
                                    </span>
                                    {summary.n.toLocaleString()}
                                    {summary.nExcluded !== null
                                      ? ` · Excluded: ${summary.nExcluded.toLocaleString()} (${exclusionText})`
                                      : ""}
                                  </p>
                                )}
                                {item.truncated && (
                                  <p className="text-warning">
                                    Truncated to 60 rows (original count:{" "}
                                    {item.original_row_count ?? "unknown"}).
                                  </p>
                                )}
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {displayedRun.status === "running" &&
                displayedRun.tool_trace.length > 0 && (
                  <div className="flex items-center gap-2 text-[11px] text-muted">
                    <Loader2
                      size={12}
                      strokeWidth={1.75}
                      aria-hidden="true"
                      className="animate-spin text-accent"
                    />
                    <span>Synthesising structured findings...</span>
                  </div>
                )}
            </section>

            {/* State 2: Findings / Answer blocks */}
            {displayedRun.status === "completed" && (
              <section
                aria-label="Investigation findings"
                data-testid="assistant-findings"
                className="space-y-3 border-t border-border pt-4"
              >
                <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                  Findings & analysis
                </div>

                {displayedRun.answer_status === "unstructured" ? (
                  <div
                    data-testid="assistant-unverified-response"
                    className="space-y-2 rounded-control border border-warning/35 bg-warning-soft/60 p-3.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill
                        variant="warning"
                        label="Unverified response"
                      />
                    </div>
                    <p className="text-[11px] text-muted">
                      The assistant returned unstructured output that could not
                      be verified against tool results. Treat as unverified
                      commentary, not findings.
                    </p>
                    <div className="whitespace-pre-wrap text-[12px] leading-relaxed text-ink">
                      {displayedRun.answer_blocks
                        .map((b) => b.text)
                        .join("\n\n")}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {displayedRun.answer_blocks.map((block, idx) => (
                      <AssistantAnswerBlockCard
                        key={`${displayedRun.id}-block-${idx}`}
                        index={idx}
                        block={block}
                        warnings={warningsByBlock[idx] ?? []}
                        traceById={traceById}
                        onClickEvidence={handleEvidenceChipClick}
                      />
                    ))}
                  </div>
                )}
              </section>
            )}
          </div>
        )}

        {/* History: Previous investigations */}
        {history.length > 0 && (
          <section
            aria-label="Previous investigations"
            className="space-y-2 border-t border-border pt-4"
          >
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              <History size={12} strokeWidth={1.75} aria-hidden="true" />
              <span>Previous investigations</span>
            </div>
            <ul className="divide-y divide-border rounded-control border border-border bg-surface-subtle">
              {history.map((item) => {
                const isSelected = displayedRun?.id === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => void handleOpenHistoryRun(item)}
                      className={[
                        "flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-[12px] transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
                        isSelected ? "bg-accent-soft/50" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <span className="line-clamp-2 flex-1 text-ink">
                        {item.question}
                      </span>
                      <span className="shrink-0 text-[10px] text-muted tabular-nums">
                        {item.status} · {formatRunTimestamp(item.started_at)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </aside>
  );
}

interface AssistantAnswerBlockCardProps {
  index: number;
  block: AssistantBlock;
  warnings: AssistantWarning[];
  traceById: Record<string, AssistantToolTraceItem>;
  onClickEvidence: (callId: string) => void;
}

function AssistantAnswerBlockCard({
  index,
  block,
  warnings,
  traceById,
  onClickEvidence,
}: AssistantAnswerBlockCardProps) {
  const hasUnsupported = warnings.some((w) => w.code === "unsupported_finding");

  const renderHeaderBadge = () => {
    switch (block.type) {
      case "finding":
        return <TypeLabel type="Observed fact" />;
      case "hypothesis":
        return (
          <>
            <TypeLabel type="Hypothesis" />
            <StatusPill variant="warning" label="Needs validation" />
          </>
        );
      case "recommended_next_step":
        return <TypeLabel type="AI recommendation" />;
      case "clarifying_question":
        return <StatusPill variant="info" label="Clarifying question" />;
      case "limitation":
        return <StatusPill variant="neutral" label="Limitation" />;
      default:
        return <StatusPill variant="warning" label="Unverified response" />;
    }
  };

  return (
    <article
      data-testid={`answer-block-${index}`}
      className="space-y-2.5 rounded-control border border-border bg-surface-subtle p-3.5"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        {renderHeaderBadge()}
        {hasUnsupported && (
          <StatusPill variant="warning" label="Unsupported statement" />
        )}
      </div>

      <p className="text-[13px] leading-relaxed text-ink">{block.text}</p>

      {block.evidence_call_ids.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {block.evidence_call_ids.map((callId) => {
            const matched = traceById[callId];
            const label = matched ? `${callId} · ${matched.tool}` : callId;
            return (
              <button
                key={callId}
                type="button"
                onClick={() => onClickEvidence(callId)}
                className="inline-flex items-center gap-1 rounded-control border border-accent/30 bg-accent-soft px-2 py-0.5 font-mono text-[10px] font-semibold text-accent hover:bg-accent-soft/80 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
              >
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      )}

      {warnings.length > 0 && (
        <div
          data-testid={`block-warnings-${index}`}
          className="space-y-1.5 border-t border-warning/25 pt-2"
        >
          {warnings.map((w, wIdx) => (
            <div
              key={`${index}-warn-${wIdx}`}
              className="flex flex-col gap-1 rounded-control border border-warning/25 bg-warning-soft px-2.5 py-2 text-[11px]"
            >
              <div>
                <StatusPill variant="warning" label={warningBadgeLabel(w.code)} />
              </div>
              <p className="text-ink leading-relaxed">{w.message}</p>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
