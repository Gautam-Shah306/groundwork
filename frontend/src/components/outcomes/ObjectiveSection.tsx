import { Card, Eyebrow, TypeLabel } from "../ui";

export interface ObjectiveSectionProps {
  problemStatement?: string | null;
  objective: string;
  onObjectiveChange: (val: string) => void;
  disabled?: boolean;
}

export function ObjectiveSection({
  problemStatement,
  objective,
  onObjectiveChange,
  disabled = false,
}: ObjectiveSectionProps) {
  return (
    <Card className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-border pb-3">
        <div>
          <Eyebrow>Strategic Intent</Eyebrow>
          <h2 className="font-display text-lg text-ink font-medium">Problem & Operational Objective</h2>
        </div>
        <div className="flex items-center gap-2">
          {problemStatement ? (
            <TypeLabel type="Client statement" />
          ) : (
            <span className="text-xs text-muted italic">Brief not drafted yet</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-1.5 rounded-panel border border-border bg-surface-subtle p-3.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Problem Statement (from Discover)
          </span>
          <p className="text-sm text-ink leading-relaxed">
            {problemStatement || "No problem statement found in brief. Generate a brief in Discovery to link context."}
          </p>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="outcomes-objective" className="block text-[11px] font-semibold uppercase tracking-wider text-muted">
            Engagement Operational Objective
          </label>
          <textarea
            id="outcomes-objective"
            value={objective}
            onChange={(e) => onObjectiveChange(e.target.value)}
            disabled={disabled}
            placeholder="e.g. Reduce median first response time below 4.0 hours while improving SLA compliance..."
            rows={3}
            className="w-full resize-none rounded-control border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
          />
        </div>
      </div>
    </Card>
  );
}
