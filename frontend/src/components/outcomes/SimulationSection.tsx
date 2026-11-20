import { useState } from "react";
import { AlertTriangle, Play } from "lucide-react";
import type { SimulationParameters, SimulationResult } from "../../lib/api";
import { Button, Card, Eyebrow, TypeLabel } from "../ui";

export interface SimulationSectionProps {
  latestSimulation: SimulationResult | null;
  simulations: SimulationResult[];
  hasActiveDataset: boolean;
  onRunSimulation: (params: SimulationParameters) => Promise<void>;
  loading?: boolean;
}

export function SimulationSection({
  latestSimulation,
  simulations,
  hasActiveDataset,
  onRunSimulation,
  loading = false,
}: SimulationSectionProps) {
  const [pilotShare, setPilotShare] = useState<number>(0.25);
  const [reductionPct, setReductionPct] = useState<number>(30);
  const [adoptionPct, setAdoptionPct] = useState<number>(80);
  const [reworkShare, setReworkShare] = useState<string>("");
  const [seed, setSeed] = useState<number>(42);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setError(null);
    try {
      const rwVal = reworkShare.trim() !== "" ? parseFloat(reworkShare) : undefined;
      await onRunSimulation({
        pilot_share: pilotShare,
        reduction_pct: reductionPct,
        adoption_pct: adoptionPct,
        rework_share: rwVal !== undefined && !isNaN(rwVal) ? rwVal : undefined,
        seed,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run pilot simulation");
    }
  };

  return (
    <Card className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
        <div>
          <Eyebrow>Pre-implementation Modeling</Eyebrow>
          <div className="flex items-center gap-2">
            <h2 className="font-display text-lg text-ink font-medium">Deterministic Pilot Simulation</h2>
            <TypeLabel type="Simulated result" />
          </div>
        </div>
        <div className="text-xs text-muted">
          Pure deterministic numpy simulation with bootstrap 95% CI
        </div>
      </div>

      <div className="rounded-control bg-warning-soft/60 border border-warning/30 p-3 flex items-start gap-2.5">
        <AlertTriangle size={16} className="text-warning shrink-0 mt-0.5" />
        <div className="text-xs text-ink space-y-0.5">
          <div className="font-semibold text-warning">Simulation is not empirical evidence</div>
          <p className="text-muted leading-relaxed">
            The simulation applies assumed effects to historical tickets; it illustrates what the assumptions imply mathematically, but does not provide evidence that an intervention will work in production.
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-error-soft text-error border border-error/30 rounded-control text-xs">
          {error}
        </div>
      )}

      {/* Parameter Controls */}
      <div className="rounded-panel border border-border bg-surface-subtle p-4 space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Simulation Assumptions</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="font-medium text-ink">Pilot Group Share</label>
              <span className="font-mono text-muted">{Math.round(pilotShare * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={pilotShare}
              onChange={(e) => setPilotShare(parseFloat(e.target.value))}
              disabled={loading || !hasActiveDataset}
              className="w-full accent-accent cursor-pointer disabled:opacity-50"
            />
            <span className="text-[10px] text-muted">Fraction of tickets routed to pilot</span>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="font-medium text-ink">Triage Reduction</label>
              <span className="font-mono text-muted">{reductionPct}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="90"
              step="5"
              value={reductionPct}
              onChange={(e) => setReductionPct(parseInt(e.target.value, 10))}
              disabled={loading || !hasActiveDataset}
              className="w-full accent-accent cursor-pointer disabled:opacity-50"
            />
            <span className="text-[10px] text-muted">Assumed % reduction in triage time</span>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="font-medium text-ink">Adoption Rate</label>
              <span className="font-mono text-muted">{adoptionPct}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="100"
              step="5"
              value={adoptionPct}
              onChange={(e) => setAdoptionPct(parseInt(e.target.value, 10))}
              disabled={loading || !hasActiveDataset}
              className="w-full accent-accent cursor-pointer disabled:opacity-50"
            />
            <span className="text-[10px] text-muted">Agent adherence to routing/suggestions</span>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="font-medium text-ink">Random Seed</label>
              <span className="font-mono text-muted">{seed}</span>
            </div>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value, 10) || 42)}
              disabled={loading || !hasActiveDataset}
              className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1 text-ink focus:outline-none focus:border-accent disabled:opacity-50 font-mono"
            />
            <span className="text-[10px] text-muted">Ensures exact mathematical reproducibility</span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-border">
          <div className="flex items-center gap-2 text-xs">
            <label className="text-muted">Manual Rework Share (optional):</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              placeholder="e.g. 0.15"
              value={reworkShare}
              onChange={(e) => setReworkShare(e.target.value)}
              className="w-24 text-xs rounded border border-border bg-surface px-2 py-0.5 text-ink font-mono"
            />
            <span className="text-[10px] text-muted">(Defaults to latest evaluation proxy if empty)</span>
          </div>

          <Button
            onClick={handleRun}
            disabled={loading || !hasActiveDataset}
            className="gap-1.5"
          >
            <Play size={13} fill="currentColor" /> Run Simulation
          </Button>
        </div>
      </div>

      {/* Latest Simulation Results */}
      {latestSimulation && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink flex items-center gap-2">
              <span>Simulation Outcome (Run #{latestSimulation.id})</span>
              <span className="text-[10px] text-muted font-normal lowercase font-mono">
                source: {latestSimulation.rework_share_source}
              </span>
            </h3>
            <span className="text-xs text-muted font-mono">
              N={latestSimulation.sample_sizes.n} (Pilot: {latestSimulation.sample_sizes.n_pilot}, Comp: {latestSimulation.sample_sizes.n_comparison})
            </span>
          </div>

          {/* Headline Metric Comparison Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-panel border border-border bg-surface p-4 space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                Median FRT Comparison
              </span>
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-xs text-muted">Comparison Group</div>
                  <div className="font-mono text-lg font-bold text-ink">
                    {latestSimulation.comparison_group.median.toFixed(2)}h
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted">Pilot After</div>
                  <div className="font-mono text-lg font-bold text-success">
                    {latestSimulation.pilot_group_after.median.toFixed(2)}h
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-panel border border-border bg-surface p-4 space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                Simulated Median Effect
              </span>
              <div className="font-mono text-2xl font-bold text-ink">
                {latestSimulation.effect.difference_of_medians_hours > 0 ? "+" : ""}
                {latestSimulation.effect.difference_of_medians_hours.toFixed(2)}h
              </div>
              <div className="text-[11px] text-muted font-mono">
                95% Bootstrap CI: [{latestSimulation.effect.bootstrap_ci_95[0].toFixed(2)}h, {latestSimulation.effect.bootstrap_ci_95[1].toFixed(2)}h]
              </div>
            </div>

            <div className="rounded-panel border border-border bg-surface p-4 space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                SLA Attainment Rate
              </span>
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-xs text-muted">Comparison Group</div>
                  <div className="font-mono text-lg font-bold text-ink">
                    {latestSimulation.comparison_group.sla_attainment_pct.toFixed(1)}%
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted">Pilot After</div>
                  <div className="font-mono text-lg font-bold text-success">
                    {latestSimulation.pilot_group_after.sla_attainment_pct.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sensitivity Grid */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
                Sensitivity Grid (Difference in Median FRT, Hours)
              </h4>
              <span className="text-[10px] text-muted font-mono">Reduction % × Adoption %</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-center border-collapse text-xs border border-border">
                <thead>
                  <tr className="bg-surface-subtle border-b border-border text-muted font-medium uppercase tracking-wider">
                    <th className="py-2 px-3 text-left">Triage Reduction \ Adoption</th>
                    <th className="py-2 px-3">50% Adoption</th>
                    <th className="py-2 px-3">80% Adoption</th>
                    <th className="py-2 px-3">100% Adoption</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[25, 50, 75].map((red) => (
                    <tr key={red}>
                      <td className="py-2.5 px-3 text-left font-medium text-ink bg-surface-subtle">
                        {red}% Reduction
                      </td>
                      {[50, 80, 100].map((adp) => {
                        const cell = latestSimulation.sensitivity_grid.find(
                          (c) => c.reduction_pct === red && c.adoption_pct === adp
                        );
                        return (
                          <td key={adp} className="py-2.5 px-3 font-mono font-medium text-ink">
                            {cell ? `${cell.difference_hours > 0 ? "+" : ""}${cell.difference_hours.toFixed(2)}h` : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {simulations.length > 1 && (
        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Run History ({simulations.length} runs)
          </h4>
          <div className="flex flex-wrap gap-2">
            {simulations.map((s) => (
              <span
                key={s.id}
                className={`text-[11px] font-mono px-2 py-1 rounded border ${
                  latestSimulation?.id === s.id
                    ? "bg-accent-soft text-accent border-accent/30 font-semibold"
                    : "bg-surface-subtle text-muted border-border"
                }`}
              >
                #{s.id}: diff {s.effect.difference_of_medians_hours.toFixed(2)}h (p={Math.round(s.parameters.pilot_share * 100)}%, r={s.parameters.reduction_pct}%)
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
