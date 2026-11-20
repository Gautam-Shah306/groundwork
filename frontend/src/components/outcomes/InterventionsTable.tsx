import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type {
  Intervention,
  InterventionCreateInput,
  InterventionUpdateInput,
} from "../../lib/api";
import { Button, Card, Eyebrow } from "../ui";

export interface InterventionsTableProps {
  interventions: Intervention[];
  onAddIntervention: (input: InterventionCreateInput) => Promise<void>;
  onUpdateIntervention: (id: number, input: InterventionUpdateInput) => Promise<void>;
  onDeleteIntervention: (id: number) => Promise<void>;
  loading?: boolean;
}

export function InterventionsTable({
  interventions,
  onAddIntervention,
  onUpdateIntervention,
  onDeleteIntervention,
  loading = false,
}: InterventionsTableProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [impact, setImpact] = useState<number>(3);
  const [effort, setEffort] = useState<number>(3);
  const [risk, setRisk] = useState<number>(2);
  const [rationale, setRationale] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const sortedInterventions = [...interventions].sort((a, b) => b.score - a.score);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) {
      setFormError("Intervention name is required.");
      return;
    }
    try {
      await onAddIntervention({
        name: name.trim(),
        description: description.trim(),
        impact,
        effort,
        risk,
        rationale: rationale.trim(),
        status: "proposed",
      });
      setName("");
      setDescription("");
      setImpact(3);
      setEffort(3);
      setRisk(2);
      setRationale("");
      setIsAdding(false);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to create intervention");
    }
  };

  const handleStatusChange = async (id: number, newStatus: "proposed" | "selected" | "rejected") => {
    await onUpdateIntervention(id, { status: newStatus });
  };

  return (
    <Card className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
        <div>
          <Eyebrow>Operational Initiatives</Eyebrow>
          <h2 className="font-display text-lg text-ink font-medium">Intervention Prioritisation</h2>
        </div>
        <div>
          {!isAdding && (
            <Button
              variant="secondary"
              onClick={() => setIsAdding(true)}
              disabled={loading}
              className="gap-1.5"
            >
              <Plus size={14} /> Add Intervention
            </Button>
          )}
        </div>
      </div>

      <p className="text-xs text-muted">
        Candidate interventions ranked by multi-criteria weighted scoring:{" "}
        <span className="font-mono text-ink">0.5×Impact + 0.3×(6-Effort) + 0.2×(6-Risk)</span>.
      </p>

      {isAdding && (
        <form onSubmit={handleSubmit} className="rounded-panel border border-border bg-surface-subtle p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">New Custom Intervention</h3>
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. VIP Triage Fast-track"
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Operational purpose"
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Impact (1–5)
              </label>
              <select
                value={impact}
                onChange={(e) => setImpact(parseInt(e.target.value, 10))}
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <option key={v} value={v}>
                    {v} {v === 5 ? "(Highest)" : v === 1 ? "(Lowest)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Effort (1–5)
              </label>
              <select
                value={effort}
                onChange={(e) => setEffort(parseInt(e.target.value, 10))}
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <option key={v} value={v}>
                    {v} {v === 1 ? "(Lowest work)" : v === 5 ? "(Highest work)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Risk (1–5)
              </label>
              <select
                value={risk}
                onChange={(e) => setRisk(parseInt(e.target.value, 10))}
                className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <option key={v} value={v}>
                    {v} {v === 1 ? "(Lowest risk)" : v === 5 ? "(Highest risk)" : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Rationale
            </label>
            <input
              type="text"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Why this rating was chosen"
              className="w-full text-xs rounded-control border border-border bg-surface px-2.5 py-1.5 text-ink focus:outline-none focus:border-accent"
            />
          </div>

          <div className="flex justify-end pt-1">
            <Button type="submit" disabled={loading}>
              Create Intervention
            </Button>
          </div>
        </form>
      )}

      {sortedInterventions.length === 0 ? (
        <div className="p-8 text-center text-muted text-sm border border-dashed border-border rounded-panel">
          No interventions registered.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border text-muted font-medium uppercase tracking-wider">
                <th className="py-2.5 px-3 w-10">Rank</th>
                <th className="py-2.5 px-3">Intervention</th>
                <th className="py-2.5 px-3 text-center">Impact</th>
                <th className="py-2.5 px-3 text-center">Effort</th>
                <th className="py-2.5 px-3 text-center">Risk</th>
                <th className="py-2.5 px-3 text-center">Score</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sortedInterventions.map((inter, idx) => (
                <tr key={inter.id} className="hover:bg-surface-subtle transition-colors">
                  <td className="py-3 px-3 font-mono text-muted text-center font-medium">
                    #{idx + 1}
                  </td>

                  <td className="py-3 px-3">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-ink">{inter.name}</span>
                        <span className="text-[10px] text-muted uppercase tracking-wider border border-border px-1.5 py-0.2 rounded">
                          {inter.origin}
                        </span>
                      </div>
                      {inter.description && (
                        <div className="text-[11px] text-muted">{inter.description}</div>
                      )}
                      {inter.rationale && (
                        <div className="text-[10px] text-muted italic">Note: {inter.rationale}</div>
                      )}
                    </div>
                  </td>

                  <td className="py-3 px-3 text-center font-mono font-medium text-ink">
                    {inter.impact} / 5
                  </td>
                  <td className="py-3 px-3 text-center font-mono font-medium text-ink">
                    {inter.effort} / 5
                  </td>
                  <td className="py-3 px-3 text-center font-mono font-medium text-ink">
                    {inter.risk} / 5
                  </td>

                  <td className="py-3 px-3 text-center">
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-accent-soft text-accent border border-accent/20">
                      {inter.score.toFixed(1)}
                    </span>
                  </td>

                  <td className="py-3 px-3">
                    <select
                      value={inter.status}
                      onChange={(e) =>
                        handleStatusChange(
                          inter.id,
                          e.target.value as "proposed" | "selected" | "rejected"
                        )
                      }
                      className="text-xs rounded border border-border bg-surface px-2 py-1 text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="proposed">Proposed</option>
                      <option value="selected">Selected</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </td>

                  <td className="py-3 px-3 text-right">
                    <button
                      type="button"
                      onClick={() => onDeleteIntervention(inter.id)}
                      className="text-muted hover:text-error p-1 transition-colors"
                      title="Delete Intervention"
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
