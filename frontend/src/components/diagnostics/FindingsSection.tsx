import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Card,
  Eyebrow,
  StatusPill,
  TypeLabel,
  type StatusPillVariant,
} from "../ui";
import type {
  DiagnosticFinding,
  MetricResultRecord,
  ValidationQuestionItem,
} from "../../lib/api";

const STRENGTH_ORDER: Record<string, number> = {
  strong: 0,
  moderate: 1,
  weak: 2,
  info: 3,
};

const STRENGTH_LABELS: Record<string, string> = {
  strong: "Strong",
  moderate: "Moderate",
  weak: "Weak",
  info: "Info",
};

const STRENGTH_VARIANTS: Record<string, StatusPillVariant> = {
  strong: "danger",
  moderate: "warning",
  weak: "neutral",
  info: "info",
};

export interface FindingsSectionProps {
  findings: DiagnosticFinding[];
  metrics: Record<string, MetricResultRecord>;
  validationQuestions: ValidationQuestionItem[];
}

export function FindingsSection({
  findings,
  metrics,
  validationQuestions,
}: FindingsSectionProps) {
  const [expandedEvidence, setExpandedEvidence] = useState<
    Record<string, boolean>
  >({});

  const orderedFindings = [...findings].sort((a, b) => {
    const rankA =
      a.status === "insufficient_data" || !a.strength
        ? 99
        : (STRENGTH_ORDER[a.strength] ?? 99);
    const rankB =
      b.status === "insufficient_data" || !b.strength
        ? 99
        : (STRENGTH_ORDER[b.strength] ?? 99);
    if (rankA !== rankB) {
      return rankA - rankB;
    }
    return a.id.localeCompare(b.id);
  });

  const toggleEvidence = (id: string) => {
    setExpandedEvidence((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      <section
        id="section-findings"
        aria-label="Rule-based diagnostic findings"
        className="space-y-4"
      >
        <div className="space-y-1">
          <Eyebrow>Evidence-backed findings</Eyebrow>
          <h2 className="text-[20px] font-semibold text-ink">
            Diagnostic findings
          </h2>
          <p className="text-[12px] text-muted">
            Deterministic rule-based observations separated from working
            hypotheses requiring client validation.
          </p>
        </div>

        <div className="space-y-4">
          {orderedFindings.map((finding) => {
            const isEvidenceOpen = Boolean(expandedEvidence[finding.id]);
            const isInsufficient = finding.status === "insufficient_data";

            return (
              <article
                key={finding.id}
                data-testid={`finding-${finding.id}`}
                className="rounded-card border border-border bg-surface p-5 space-y-4"
              >
                <header className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <span className="font-mono text-[11px] font-semibold text-muted">
                      {finding.id}
                    </span>
                    <h3 className="text-[15px] font-semibold text-ink">
                      {finding.title}
                    </h3>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {isInsufficient ? (
                      <StatusPill variant="neutral" label="Insufficient data" />
                    ) : finding.strength ? (
                      <StatusPill
                        variant={STRENGTH_VARIANTS[finding.strength] ?? "neutral"}
                        label={STRENGTH_LABELS[finding.strength] ?? finding.strength}
                      />
                    ) : null}
                  </div>
                </header>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="space-y-2 rounded-control border border-border bg-surface-subtle p-4">
                    <TypeLabel type="Observed fact" />
                    <p className="text-[13px] leading-relaxed text-ink">
                      {finding.observation.text}
                    </p>
                  </div>

                  <div className="space-y-2 rounded-control border border-border bg-surface-subtle p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <TypeLabel type="Hypothesis" />
                      <StatusPill variant="warning" label="Needs validation" />
                    </div>
                    <p className="text-[13px] leading-relaxed text-ink">
                      {finding.hypothesis.text}
                    </p>
                  </div>
                </div>

                {/* Expandable evidence */}
                <div className="border-t border-border pt-3 space-y-3">
                  <button
                    type="button"
                    aria-expanded={isEvidenceOpen}
                    onClick={() => toggleEvidence(finding.id)}
                    className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    {isEvidenceOpen ? (
                      <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" />
                    ) : (
                      <ChevronRight size={14} strokeWidth={1.75} aria-hidden="true" />
                    )}
                    <span>Evidence ({finding.evidence.length})</span>
                  </button>

                  {isEvidenceOpen && (
                    <div className="overflow-x-auto rounded-control border border-border bg-surface-subtle p-3">
                      <table className="w-full border-collapse text-left text-[12px]">
                        <thead>
                          <tr className="border-b border-border text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                            <th className="py-1.5 pr-3">Metric ID</th>
                            <th className="py-1.5 pr-3">Label & parameters</th>
                            <th className="py-1.5 pr-3 text-right">Value</th>
                            <th className="py-1.5 pr-3 text-right">n</th>
                            <th className="py-1.5">Definition</th>
                          </tr>
                        </thead>
                        <tbody>
                          {finding.evidence.map((ev, idx) => {
                            const refMetric = metrics[ev.metric_id];
                            const paramsText =
                              Object.keys(ev.params).length > 0
                                ? JSON.stringify(ev.params)
                                : "default";
                            return (
                              <tr
                                key={`${finding.id}-${ev.metric_id}-${idx}`}
                                className="border-b border-border last:border-b-0"
                              >
                                <td className="py-2 pr-3 font-mono text-[11px] text-ink">
                                  {ev.metric_id}
                                </td>
                                <td className="py-2 pr-3 text-ink">
                                  <div>{ev.label}</div>
                                  <div className="font-mono text-[10px] text-muted">
                                    {paramsText}
                                  </div>
                                </td>
                                <td className="py-2 pr-3 text-right font-semibold tabular-nums text-ink">
                                  {ev.value !== null && ev.value !== undefined
                                    ? `${ev.value} ${ev.unit}`
                                    : "—"}
                                </td>
                                <td className="py-2 pr-3 text-right tabular-nums text-muted">
                                  {ev.n.toLocaleString()}
                                </td>
                                <td className="py-2 text-[11px] text-muted">
                                  {refMetric?.definition ?? "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Limitations & finding validation questions */}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 text-[12px]">
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                        Limitations
                      </div>
                      <ul className="list-disc pl-4 space-y-1 text-muted">
                        {finding.limitations.map((lim) => (
                          <li key={lim}>{lim}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="space-y-1.5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                        Validation questions
                      </div>
                      <ul className="space-y-1.5">
                        {finding.validation_questions.map((q) => (
                          <li key={q.text} className="flex items-start gap-2 text-ink">
                            <StatusPill variant="neutral" label="Template question" />
                            <span>{q.text}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section id="section-questions" aria-label="Questions for client validation">
        <Card
          title="Questions for client validation"
          description="Combined checklist of template questions to confirm with operational stakeholders before acting."
        >
          <ul className="divide-y divide-border">
            {validationQuestions.map((q) => (
              <li
                key={q.text}
                className="flex flex-wrap items-start gap-2.5 py-3 first:pt-0 last:pb-0 text-[13px] text-ink"
              >
                <StatusPill variant="neutral" label="Template question" />
                {q.finding_id && (
                  <span className="font-mono text-[11px] font-semibold text-muted">
                    {q.finding_id}
                  </span>
                )}
                <span className="flex-1">{q.text}</span>
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </div>
  );
}
