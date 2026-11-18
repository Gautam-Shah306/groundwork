import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { fetchHealth, type HealthPayload } from "../../lib/api";

type HealthState =
  | { status: "checking" }
  | { status: "operational"; payload: HealthPayload }
  | { status: "unavailable"; reason: string };

export function SystemStatus() {
  const [state, setState] = useState<HealthState>({ status: "checking" });

  const checkHealth = useCallback(async (signal?: AbortSignal) => {
    setState({ status: "checking" });
    try {
      const payload = await fetchHealth(signal);
      if (payload.status === "ok") {
        setState({ status: "operational", payload });
      } else {
        setState({
          status: "unavailable",
          reason: "Backend reported an unexpected status. Check API logs.",
        });
      }
    } catch (error) {
      if (signal?.aborted) {
        return;
      }
      const detail =
        error instanceof Error && error.message
          ? error.message
          : "Network request failed";
      setState({
        status: "unavailable",
        reason: `Start the backend API or verify the /api proxy (${detail}).`,
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(controller.signal);
    return () => controller.abort();
  }, [checkHealth]);

  if (state.status === "checking") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-1.5 rounded-pill border border-border bg-surface-subtle px-2.5 py-1 text-[11px] font-medium text-muted"
      >
        <Loader2
          size={14}
          strokeWidth={1.75}
          aria-hidden="true"
          className="animate-spin text-accent"
        />
        <span>System status: checking</span>
      </div>
    );
  }

  if (state.status === "operational") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-1.5 rounded-pill border border-success/20 bg-success-soft px-2.5 py-1 text-[11px] font-semibold text-success"
      >
        <CheckCircle2 size={14} strokeWidth={1.75} aria-hidden="true" />
        <span>System status: operational</span>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-center justify-end gap-2"
    >
      <span className="inline-flex items-center gap-1.5 rounded-pill border border-danger/25 bg-danger-soft px-2.5 py-1 text-[11px] font-semibold text-danger">
        <AlertCircle size={14} strokeWidth={1.75} aria-hidden="true" />
        <span>System status: unavailable</span>
      </span>
      <span className="text-[11px] text-muted">{state.reason}</span>
      <button
        type="button"
        onClick={() => void checkHealth()}
        className="rounded-control border border-border bg-surface px-2 py-0.5 text-[11px] font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        Retry
      </button>
    </div>
  );
}
