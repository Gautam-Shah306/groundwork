import { Database, Fingerprint, Layers, Sparkles } from "lucide-react";
import { Card, Eyebrow, KpiTile, TypeLabel } from "../ui";
import type { EvalRunSummary } from "../../lib/api";

export interface ResultsSummaryProps {
  run: EvalRunSummary;
}

export function ResultsSummary({ run }: ResultsSummaryProps) {
  const results = run.results;
  if (!results || !results.summary) {
    return null;
  }

  const { summary } = results;
  const wilsonLow = Math.round(summary.category_accuracy_wilson[0] * 1000) / 10;
  const wilsonHigh = Math.round(summary.category_accuracy_wilson[1] * 1000) / 10;
  const wilsonSubtitle = `Wilson 95%: [${wilsonLow}%, ${wilsonHigh}%]`;

  const durationSec =
    run.started_at && run.finished_at
      ? Math.max(
          1,
          Math.round(
            (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000
          )
        )
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>EVALUATION RESULTS</Eyebrow>
          <h2 className="font-display text-[26px] font-normal tracking-tight text-ink">
            Benchmark Summary
          </h2>
        </div>

        <TypeLabel type="Measured outcome" />
      </div>

      {/* KPI Tiles grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiTile
          name="Strict Category Acc."
          value={`${summary.category_accuracy_pct}%`}
          period={wilsonSubtitle}
          statusLabel="Primary"
          statusVariant="success"
        />

        {summary.failed > 0 && (
          <KpiTile
            name="Completed-only Acc."
            value={`${Math.round(summary.category_accuracy_completed * 1000) / 10}%`}
            period={`${summary.completed} completed items`}
            statusVariant="info"
          />
        )}

        <KpiTile
          name="Lenient Category Acc."
          value={`${Math.round(summary.lenient_category_accuracy * 1000) / 10}%`}
          period="Credits secondary on ambiguous"
          statusVariant="neutral"
        />

        <KpiTile
          name="Priority Accuracy"
          value={`${summary.priority_accuracy_pct}%`}
          period="Deterministic rules"
          statusVariant="success"
        />

        <KpiTile
          name="Queue Routing Acc."
          value={`${summary.queue_accuracy_pct}%`}
          period="Category + overrides"
          statusVariant="neutral"
        />

        <KpiTile
          name="Reviewer Change Proxy"
          value={`${summary.reviewer_change_proxy_pct}%`}
          period="Intervention required"
          statusVariant={summary.reviewer_change_proxy_pct > 20 ? "warning" : "neutral"}
        />
      </div>

      {/* Run Metadata Card */}
      <Card className="p-4 bg-surface-subtle text-[12px] text-muted">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-6">
            <span className="flex items-center gap-1.5 font-mono text-ink">
              <Sparkles size={13} className="text-muted" />
              {run.model}
            </span>

            <span className="flex items-center gap-1.5">
              <Layers size={13} className="text-muted" />
              {run.sample_size} tickets evaluated
            </span>

            {run.usage && (
              <span className="flex items-center gap-1.5 font-mono">
                <Database size={13} className="text-muted" />
                {run.usage.total_tokens.toLocaleString()} tokens ({run.usage.provider_calls} calls)
              </span>
            )}

            {durationSec !== null && (
              <span>Duration: {Math.floor(durationSec / 60)}m {durationSec % 60}s</span>
            )}
          </div>

          <div
            className="flex items-center gap-1.5 font-mono text-[11px] text-muted"
            title={`Full config fingerprint: ${run.config_fingerprint}`}
          >
            <Fingerprint size={13} className="text-muted" />
            <span>Fingerprint: {run.config_fingerprint.slice(0, 12)}…</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
