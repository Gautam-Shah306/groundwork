import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Eyebrow, KpiTile } from "../ui";
import type { DiagnosticsKpi } from "../../lib/api";
import { formatShortDate } from "../../lib/format";

function formatPeriod(start: string | null, end: string | null): string {
  if (!start || !end) {
    return "Period unavailable";
  }
  return `${formatShortDate(start)} – ${formatShortDate(end)}`;
}

export interface DiagnosticsKpiGridProps {
  kpis: DiagnosticsKpi[];
}

export function DiagnosticsKpiGrid({ kpis }: DiagnosticsKpiGridProps) {
  const [openExpander, setOpenExpander] = useState<Record<string, boolean>>({});

  const toggle = (metricId: string) => {
    setOpenExpander((prev) => ({ ...prev, [metricId]: !prev[metricId] }));
  };

  return (
    <section id="section-kpis" aria-label="Operational KPI summary" className="space-y-4">
      <div className="space-y-1">
        <Eyebrow>Operational KPIs</Eyebrow>
        <h2 className="text-[20px] font-semibold text-ink">
          Baseline summary
        </h2>
        <p className="text-[12px] text-muted">
          Deterministic baseline values computed from stored rows. No targets or
          improvement percentages are shown without client agreement.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {kpis.map((kpi) => {
          const isOpen = Boolean(openExpander[kpi.metric_id]);
          const exclusionEntries = Object.entries(kpi.exclusions);
          const displayValue =
            kpi.value === null ? "—" : kpi.value.toLocaleString();

          return (
            <div
              key={kpi.metric_id}
              data-testid={`kpi-card-${kpi.metric_id}`}
              className="flex flex-col rounded-card border border-border bg-surface"
            >
              <KpiTile
                name={kpi.name}
                value={displayValue}
                unit={kpi.unit}
                period={formatPeriod(kpi.period_start, kpi.period_end)}
                className="border-0 rounded-b-none"
              />

              <div className="space-y-2 border-t border-border px-5 py-3 text-[11px]">
                <div className="flex items-center justify-between gap-2 text-muted tabular-nums">
                  <span>Sample used</span>
                  <span className="font-semibold text-ink">
                    n = {kpi.n.toLocaleString()}
                  </span>
                </div>

                {kpi.note && (
                  <p className="rounded-control border border-warning/25 bg-warning-soft px-2.5 py-1.5 text-[11px] text-warning">
                    {kpi.note}
                  </p>
                )}

                <button
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => toggle(kpi.metric_id)}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  {isOpen ? (
                    <ChevronDown size={13} strokeWidth={1.75} aria-hidden="true" />
                  ) : (
                    <ChevronRight size={13} strokeWidth={1.75} aria-hidden="true" />
                  )}
                  <span>How this is calculated</span>
                </button>

                {isOpen && (
                  <div className="space-y-1.5 rounded-control border border-border bg-surface-subtle p-3 text-[11px] leading-relaxed text-ink">
                    <p>
                      <span className="font-semibold">Definition:</span>{" "}
                      {kpi.definition}
                    </p>
                    <p>
                      <span className="font-semibold">Scope:</span> {kpi.scope}
                    </p>
                    <p className="tabular-nums">
                      <span className="font-semibold">Excluded rows:</span>{" "}
                      {kpi.n_excluded.toLocaleString()}
                      {exclusionEntries.length > 0
                        ? ` (${exclusionEntries
                            .map(([code, count]) => `${code}: ${count}`)
                            .join(", ")})`
                        : " (none)"}
                    </p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
