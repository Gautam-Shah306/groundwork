import { useState } from "react";
import { AlertCircle, Plus, RefreshCw, Star, Trash2 } from "lucide-react";
import type { Kpi, KpiCatalogueItem, KpiCreateInput } from "../../lib/api";
import { Button, Card, Eyebrow, StatusPill, TypeLabel } from "../ui";

export interface KpiTableProps {
  kpis: Kpi[];
  catalogue: KpiCatalogueItem[];
  hasActiveDataset: boolean;
  onAddKpi: (input: KpiCreateInput) => Promise<void>;
  onDeleteKpi: (id: number) => Promise<void>;
  onRecomputeBaseline: (id: number) => Promise<void>;
  loading?: boolean;
}

export function KpiTable({
  kpis,
  catalogue,
  hasActiveDataset,
  onAddKpi,
  onDeleteKpi,
  onRecomputeBaseline,
  loading = false,
}: KpiTableProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [selectedMetricId, setSelectedMetricId] = useState(catalogue[0]?.metric_id || "");
  const [targetValue, setTargetValue] = useState("");
  const [targetAssumption, setTargetAssumption] = useState("");
  const [isPrimary, setIsPrimary] = useState(kpis.length === 0);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);

  // Available catalogue items that are not yet added
  const existingMetricIds = new Set(kpis.map((k) => k.metric_id));
  const availableCatalogue = catalogue.filter((item) => !existingMetricIds.has(item.metric_id));

  const handleOpenAdd = () => {
    const nextMetric = availableCatalogue[0]?.metric_id || catalogue[0]?.metric_id || "";
    setSelectedMetricId(nextMetric);
    setTargetValue("");
    setTargetAssumption("");
    setIsPrimary(kpis.length === 0);
    setFormError(null);
    setIsAdding(true);
  };

  const handleSubmitAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const catItem = catalogue.find((c) => c.metric_id === selectedMetricId);
    if (!catItem) {
      setFormError("Please select a valid KPI from the catalogue.");
      return;
    }

    const tVal = targetValue.trim() !== "" ? parseFloat(targetValue) : undefined;
    if (tVal !== undefined && isNaN(tVal)) {
      setFormError("Target value must be a valid number.");
      return;
    }

    if (tVal !== undefined && targetAssumption.trim().length < 10) {
      setFormError("Target assumption is required (minimum 10 characters).");
      return;
    }

    try {
      await onAddKpi({
        metric_id: selectedMetricId,
        target_value: tVal,
        target_assumption: targetAssumption.trim() || undefined,
        is_primary: isPrimary,
      });
      setIsAdding(false);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to add KPI");
    }
  };

  const handleRecompute = async (id: number) => {
    setActionInProgress(id);
    try {
      await onRecomputeBaseline(id);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDelete = async (id: number) => {
    setActionInProgress(id);
    try {
      await onDeleteKpi(id);
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <Card className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
        <div>
          <Eyebrow>Targets & Baselines</Eyebrow>
          <h2 className="font-display text-lg text-ink font-medium">KPI Framework</h2>
        </div>
        <div>
          {!isAdding && availableCatalogue.length > 0 && (
            <Button
              variant="secondary"
              onClick={handleOpenAdd}
              disabled={loading || !hasActiveDataset}
              className="gap-1.5"
            >
              <Plus size={14} /> Add KPI Target
            </Button>
          )}
        </div>
      </div>

      {!hasActiveDataset && (
        <div className="flex items-center gap-2 p-3 bg-warning-soft border border-warning/30 rounded-control text-xs text-warning">
          <AlertCircle size={15} />
          <span>Active dataset required to compute KPI baselines. Upload or select a dataset in Diagnostics.</span>
        </div>
      )}

      {isAdding && (
        <form onSubmit={handleSubmitAdd} className="rounded-panel border border-border bg-surface-subtle p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">Add KPI from Catalogue</h3>
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="text-xs text-muted hover:text-ink"
            >
              Cancel
            </button>
          </div>

          {formError && (
            <div className="p-2 bg-error-soft text-error border border-error/30 rounded-control text-xs">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Metric
              </label>
              <select
                value={selectedMetricId}
                onChange={(e) => setSelectedMetricId(e.target.value)}
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              >
                {availableCatalogue.map((cat) => (
                  <option key={cat.metric_id} value={cat.metric_id}>
                    {cat.name} ({cat.unit})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Target Value
              </label>
              <input
                type="number"
                step="any"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                placeholder="Target number"
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Target Assumption (min 10 chars)
              </label>
              <input
                type="text"
                value={targetAssumption}
                onChange={(e) => setTargetAssumption(e.target.value)}
                placeholder="e.g. Automated routing reduces manual handling"
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <label className="flex items-center gap-2 text-xs text-ink cursor-pointer">
              <input
                type="checkbox"
                checked={isPrimary}
                onChange={(e) => setIsPrimary(e.target.checked)}
                className="rounded border-border text-accent focus:ring-accent"
              />
              Designate as Primary KPI
            </label>
            <Button type="submit" disabled={loading}>
              Save KPI
            </Button>
          </div>
        </form>
      )}

      {kpis.length === 0 ? (
        <div className="p-8 text-center text-muted text-sm border border-dashed border-border rounded-panel">
          No KPIs added yet. Add targets from the operational catalogue to establish baseline benchmarks.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border text-muted font-medium uppercase tracking-wider">
                <th className="py-2.5 px-3">Metric</th>
                <th className="py-2.5 px-3">Baseline</th>
                <th className="py-2.5 px-3">Target</th>
                <th className="py-2.5 px-3">Planned Change</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {kpis.map((kpi) => (
                <tr key={kpi.id} className="hover:bg-surface-subtle transition-colors">
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      {kpi.is_primary && (
                        <span title="Primary KPI" className="text-accent flex items-center">
                          <Star size={13} fill="currentColor" />
                        </span>
                      )}
                      <div>
                        <div className="font-medium text-ink text-xs">{kpi.name}</div>
                        <div className="text-[11px] text-muted">{kpi.definition}</div>
                      </div>
                    </div>
                  </td>

                  <td className="py-3 px-3">
                    {kpi.baseline ? (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-ink">
                          <span>{kpi.baseline.value.toFixed(2)} {kpi.unit}</span>
                          <TypeLabel type="Observed fact" className="scale-90 origin-left" />
                        </div>
                        {kpi.is_stale ? (
                          <div className="flex items-center gap-1">
                            <StatusPill variant="warning" label="Stale dataset" />
                            <button
                              type="button"
                              onClick={() => handleRecompute(kpi.id)}
                              disabled={actionInProgress === kpi.id}
                              className="text-[11px] text-accent hover:underline flex items-center gap-0.5"
                            >
                              <RefreshCw size={10} className={actionInProgress === kpi.id ? "animate-spin" : ""} />
                              Recompute
                            </button>
                          </div>
                        ) : (
                          <div className="text-[10px] text-muted font-mono">
                            N={kpi.baseline.n} tickets
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted italic">No baseline</span>
                    )}
                  </td>

                  <td className="py-3 px-3">
                    {kpi.target_value !== null ? (
                      <div className="space-y-0.5">
                        <div className="font-mono text-xs font-semibold text-ink">
                          {kpi.target_value.toFixed(2)} {kpi.unit}
                        </div>
                        {kpi.target_assumption && (
                          <div className="text-[10px] text-muted truncate max-w-[200px]" title={kpi.target_assumption}>
                            {kpi.target_assumption}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted italic">No target set</span>
                    )}
                  </td>

                  <td className="py-3 px-3">
                    {kpi.planned_change ? (
                      <div className="space-y-1">
                        <div className="font-mono text-xs font-semibold text-ink">
                          {kpi.planned_change.absolute_change > 0 ? "+" : ""}
                          {kpi.planned_change.absolute_change.toFixed(2)} {kpi.unit}
                          {" "}({kpi.planned_change.relative_change_pct > 0 ? "+" : ""}
                          {kpi.planned_change.relative_change_pct.toFixed(1)}%)
                        </div>
                        <div>
                          <TypeLabel type="Planned change, not an outcome" className="scale-90 origin-left" />
                        </div>
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>

                  <td className="py-3 px-3 text-right">
                    <button
                      type="button"
                      onClick={() => handleDelete(kpi.id)}
                      disabled={actionInProgress === kpi.id}
                      className="text-muted hover:text-error p-1 transition-colors"
                      title="Delete KPI"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
