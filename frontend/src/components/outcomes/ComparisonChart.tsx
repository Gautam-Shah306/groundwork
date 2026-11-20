import { useState } from "react";
import { BarChart3, Table as TableIcon } from "lucide-react";
import type { Kpi, SimulationResult } from "../../lib/api";
import { Button, Card, Eyebrow, TypeLabel } from "../ui";

export interface ComparisonChartProps {
  primaryKpi: Kpi | null;
  simulation: SimulationResult | null;
}

export function ComparisonChart({ primaryKpi, simulation }: ComparisonChartProps) {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");

  if (!primaryKpi && !simulation) {
    return null;
  }

  const baselineVal = primaryKpi?.baseline?.value ?? null;
  const targetVal = primaryKpi?.target_value ?? null;
  const simulatedVal = simulation?.pilot_group_after?.median ?? null;
  const compVal = simulation?.comparison_group?.median ?? null;

  const dataPoints = [
    {
      label: "Empirical Baseline",
      type: "Observed fact" as const,
      value: baselineVal,
      unit: primaryKpi?.unit ?? "h",
      description: "Historical median from active dataset",
      barClass: "bg-ink",
    },
    {
      label: "Comparison Group",
      type: "Simulated result" as const,
      value: compVal,
      unit: "h",
      description: "Untreated partition in pilot simulation",
      barClass: "bg-muted",
    },
    {
      label: "Simulated Pilot After",
      type: "Simulated result" as const,
      value: simulatedVal,
      unit: "h",
      description: "Modelled median after assumed triage reduction",
      barClass: "bg-accent",
    },
    {
      label: "Target Value",
      type: "Planned change, not an outcome" as const,
      value: targetVal,
      unit: primaryKpi?.unit ?? "h",
      description: "Operator goal based on proposed intervention",
      barClass: "bg-surface border-2 border-dashed border-accent",
    },
  ].filter((p) => p.value !== null);

  const maxValue = Math.max(...dataPoints.map((p) => p.value as number), 1);

  return (
    <Card className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
        <div>
          <Eyebrow>Visual Comparison</Eyebrow>
          <h2 className="font-display text-lg text-ink font-medium">Trajectory & Scenario Benchmarks</h2>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant={viewMode === "chart" ? "primary" : "secondary"}
            onClick={() => setViewMode("chart")}
            className="gap-1 text-xs"
          >
            <BarChart3 size={13} /> Chart
          </Button>
          <Button
            variant={viewMode === "table" ? "primary" : "secondary"}
            onClick={() => setViewMode("table")}
            className="gap-1 text-xs"
          >
            <TableIcon size={13} /> View as table
          </Button>
        </div>
      </div>

      {viewMode === "chart" ? (
        <div className="space-y-4 py-2">
          {dataPoints.map((pt) => {
            const widthPct = Math.min(100, Math.max(8, ((pt.value as number) / maxValue) * 100));
            return (
              <div key={pt.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink">{pt.label}</span>
                    <TypeLabel type={pt.type} className="scale-90 origin-left" />
                  </div>
                  <span className="font-mono font-semibold text-ink">
                    {(pt.value as number).toFixed(2)} {pt.unit}
                  </span>
                </div>
                <div className="h-6 w-full rounded bg-surface-subtle border border-border overflow-hidden">
                  <div
                    style={{ width: `${widthPct}%` }}
                    className={`h-full rounded-sm transition-all duration-300 ${pt.barClass}`}
                  />
                </div>
                <div className="text-[10px] text-muted">{pt.description}</div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border text-muted font-medium uppercase tracking-wider">
                <th className="py-2.5 px-3">Scenario</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3 font-mono text-right">Value</th>
                <th className="py-2.5 px-3">Context</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {dataPoints.map((pt) => (
                <tr key={pt.label} className="hover:bg-surface-subtle">
                  <td className="py-3 px-3 font-medium text-ink">{pt.label}</td>
                  <td className="py-3 px-3">
                    <TypeLabel type={pt.type} />
                  </td>
                  <td className="py-3 px-3 font-mono font-semibold text-ink text-right">
                    {(pt.value as number).toFixed(2)} {pt.unit}
                  </td>
                  <td className="py-3 px-3 text-muted text-[11px]">{pt.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
