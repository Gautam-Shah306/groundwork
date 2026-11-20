import { useState } from "react";
import { ChevronDown, ChevronUp, Clock, Database, Fingerprint, Layers, Sparkles } from "lucide-react";
import { Card, Eyebrow, TypeLabel } from "../ui";
import type { EvalRunSummary } from "../../lib/api";

export interface ResultsSummaryProps {
  run: EvalRunSummary;
}

export function ResultsSummary({ run }: ResultsSummaryProps) {
  const [expandedInfo, setExpandedInfo] = useState<Record<string, boolean>>({});

  const toggleInfo = (key: string) => {
    setExpandedInfo((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const results = run.results;
  if (!results || !results.summary) {
    return null;
  }

  const { summary } = results;
  const total = summary.total_tickets || run.sample_size;
  const wilsonLow = Math.round((summary.category_accuracy_wilson?.[0] || 0) * 1000) / 10;
  const wilsonHigh = Math.round((summary.category_accuracy_wilson?.[1] || 0) * 1000) / 10;
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

  const runDateStr = run.started_at
    ? new Date(run.started_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Unknown date";

  const headlineMetrics = [
    {
      key: "category",
      title: "Strict Category Acc.",
      value: `${summary.category_accuracy_pct}%`,
      subtitle: wilsonSubtitle,
      n: `n = ${total}`,
      formula:
        "Strict category accuracy = (correctly predicted category) / (total evaluated tickets). Failed items count as incorrect. Evaluated against held-out ground truth.",
    },
    {
      key: "priority",
      title: "Priority Accuracy",
      value: `${summary.priority_accuracy_pct}%`,
      subtitle: summary.priority_accuracy_completed
        ? `Completed: ${Math.round(summary.priority_accuracy_completed * 1000) / 10}%`
        : "Deterministic rules",
      n: `n = ${total}`,
      formula:
        "Priority accuracy = (tickets where evaluate_priority on predicted signals matches true priority) / (total tickets). Pure deterministic rule evaluation on predicted signals.",
    },
    {
      key: "queue",
      title: "Queue Accuracy",
      value: `${summary.queue_accuracy_pct}%`,
      subtitle: "Category + overrides",
      n: `n = ${total}`,
      formula:
        "Queue accuracy = (tickets with predicted queue matching expected queue derived from true category and true signals) / (total tickets).",
    },
    {
      key: "proxy",
      title: "Reviewer-Change Proxy",
      value: `${summary.reviewer_change_proxy_pct}%`,
      subtitle: "Intervention needed",
      n: `n = ${total}`,
      formula:
        "Reviewer-change proxy = share of evaluated tickets where category OR priority OR queue is wrong, or there is no prediction. Signals are not part of it; labelled a proxy, not an override rate.",
    },
    {
      key: "failed",
      title: "Failed Items",
      value: `${summary.failed}`,
      subtitle: summary.failed > 0 ? "Model or timeout errors" : "Zero errors",
      n: `n = ${total}`,
      formula:
        "Failed items = count of tickets that failed to classify due to rate limits, timeouts, schema violations, or provider errors.",
    },
    {
      key: "missed_high",
      title: "Missed-High Count",
      value: `${results.priority_metrics?.missed_high?.count ?? summary.missed_high_count ?? 0}`,
      subtitle: results.priority_metrics?.missed_high?.rate
        ? `Rate: ${Math.round(results.priority_metrics.missed_high.rate * 1000) / 10}%`
        : "True high predicted lower",
      n: `completed true-high`,
      formula:
        "Missed-high = count and share of completed true-high tickets predicted as medium or low. Truth-high tickets with no prediction are reported separately.",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header Info Card */}
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

            <span className="flex items-center gap-1.5 font-mono">
              <Clock size={13} className="text-muted" />
              {runDateStr}
            </span>

            {durationSec !== null && (
              <span>Duration: {Math.floor(durationSec / 60)}m {durationSec % 60}s</span>
            )}

            {run.usage && (
              <span className="flex items-center gap-1.5 font-mono">
                <Database size={13} className="text-muted" />
                {run.usage.total_tokens?.toLocaleString()} tokens ({run.usage.provider_calls} calls)
              </span>
            )}
          </div>

          <div
            className="flex items-center gap-1.5 font-mono text-[11px] text-muted"
            title={`Full config fingerprint: ${run.config_fingerprint}`}
          >
            <Fingerprint size={13} className="text-muted" />
            <span>Fingerprint: {run.config_fingerprint.slice(0, 8)}</span>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>EVALUATION RESULTS</Eyebrow>
          <h2 className="font-display text-[26px] font-normal tracking-tight text-ink">
            Benchmark Headline Metrics
          </h2>
        </div>
      </div>

      {/* KPI Tiles grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {headlineMetrics.map((tile) => (
          <div
            key={tile.key}
            className="flex flex-col justify-between rounded-card border border-border bg-surface p-4 space-y-3"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[12px] font-semibold text-muted uppercase tracking-wider">
                  {tile.title}
                </span>
                <TypeLabel type="Measured outcome" />
              </div>
              <p className="text-[11px] text-muted/80">on synthetic tickets</p>
            </div>

            <div className="space-y-1">
              <div className="font-mono text-[24px] font-bold text-ink">
                {tile.value}
              </div>
              <div className="text-[11px] text-muted font-mono">
                {tile.subtitle}
              </div>
              <div className="text-[10px] text-muted/70">
                {tile.n}
              </div>
            </div>

            {/* How this is calculated expander */}
            <div className="border-t border-border/50 pt-2">
              <button
                type="button"
                onClick={() => toggleInfo(tile.key)}
                className="flex items-center justify-between w-full text-left text-[11px] text-accent hover:text-accent-hover font-medium"
              >
                <span>How this is calculated</span>
                {expandedInfo[tile.key] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {expandedInfo[tile.key] && (
                <p className="mt-1.5 text-[11px] text-muted leading-relaxed bg-surface-subtle p-2 rounded border border-border/40">
                  {tile.formula}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Permanent Limitations Note */}
      <Card className="p-4 bg-surface-subtle border-border/80 text-[12px] text-muted space-y-2">
        <h4 className="font-semibold text-ink uppercase tracking-wider text-[11px]">
          Evaluation Methodology &amp; Limitations
        </h4>
        <p>
          Synthetic tickets were constructed from representative support scenarios; labels are correct by design.
          Single run benchmark; accuracy here may overstate real-world open-domain performance. Wilson 95% score
          intervals indicate uncertainty due to sample size. The reviewer-change proxy reflects cases where
          human correction would be required across category, priority, or queue, but is not a measured production override rate.
        </p>
      </Card>
    </div>
  );
}
