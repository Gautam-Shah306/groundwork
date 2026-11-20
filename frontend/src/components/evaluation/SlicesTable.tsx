import { Card, Eyebrow, StatusPill } from "../ui";
import type { EvalResults } from "../../lib/api";

export interface SlicesTableProps {
  slices: EvalResults["slices"];
}

const SLICE_DISPLAY_NAMES: Record<string, { label: string; desc: string }> = {
  en: {
    label: "English tickets",
    desc: "Tickets written in standard English",
  },
  hinglish: {
    label: "Hinglish tickets",
    desc: "Tickets written in Hindi transcribed into Latin alphabet",
  },
  is_ambiguous: {
    label: "Ambiguous tickets",
    desc: "Tickets straddling two distinct category definitions",
  },
  short: {
    label: "Short tickets (<100 chars)",
    desc: "Concise inquiries with minimal contextual cues",
  },
  urgency_or_delay: {
    label: "Urgency / Delay tickets",
    desc: "Tickets explicitly stating a deadline or transit delay",
  },
};

export function SlicesTable({ slices }: SlicesTableProps) {
  if (!slices || slices.length === 0) return null;

  return (
    <Card className="p-6 space-y-4">
      <div>
        <Eyebrow>DATASET SEGMENTS</Eyebrow>
        <h3 className="font-display text-[20px] font-normal text-ink">
          Performance by Subgroup Slice
        </h3>
        <p className="text-[12px] text-muted">
          Accuracy evaluated across linguistic, ambiguous, and length-based slices. Slices with n &lt; 30 are flagged as low confidence.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13px] border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface-subtle text-muted text-[11px] uppercase font-semibold">
              <th className="p-2.5">Slice</th>
              <th className="p-2.5">Description</th>
              <th className="p-2.5 text-right">Sample (n)</th>
              <th className="p-2.5 text-right">Category Acc.</th>
              <th className="p-2.5 text-right">Priority Acc.</th>
              <th className="p-2.5 text-center">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {slices.map((slice) => {
              const meta = SLICE_DISPLAY_NAMES[slice.name] || {
                label: slice.name,
                desc: "",
              };
              const catPct = Math.round(slice.category_accuracy * 1000) / 10;
              const priPct = Math.round(slice.priority_accuracy * 1000) / 10;

              return (
                <tr key={slice.name} className="border-b border-border/50 hover:bg-surface-subtle/50">
                  <td className="p-2.5 font-medium text-ink">{meta.label}</td>
                  <td className="p-2.5 text-[12px] text-muted">{meta.desc}</td>
                  <td className="p-2.5 text-right font-mono tabular-nums text-muted">{slice.count}</td>
                  <td className="p-2.5 text-right font-mono tabular-nums text-ink font-semibold">
                    {catPct}%
                  </td>
                  <td className="p-2.5 text-right font-mono tabular-nums text-ink font-semibold">
                    {priPct}%
                  </td>
                  <td className="p-2.5 text-center">
                    {slice.low_confidence ? (
                      <StatusPill variant="warning" label="Low n (<30)" />
                    ) : (
                      <StatusPill variant="neutral" label="Sufficient" />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
