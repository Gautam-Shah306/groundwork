import type { ReactNode } from "react";
import {
  BarChart3,
  CheckCircle2,
  Database,
  FlaskConical,
  HelpCircle,
  MessageSquareQuote,
  Sparkles,
} from "lucide-react";

export const EVIDENCE_TYPES = [
  "Observed fact",
  "Client statement",
  "Hypothesis",
  "AI recommendation",
  "Approved action",
  "Measured outcome",
  "Simulated result",
] as const;

export type EvidenceType = (typeof EVIDENCE_TYPES)[number];

export interface TypeLabelProps {
  type: EvidenceType;
  className?: string;
}

const TYPE_STYLES: Record<EvidenceType, string> = {
  "Observed fact": "bg-surface-subtle text-ink border-border",
  "Client statement": "bg-surface-subtle text-muted border-border",
  Hypothesis: "bg-warning-soft text-warning border-warning/25",
  "AI recommendation": "bg-accent-soft text-accent border-accent/25",
  "Approved action": "bg-success-soft text-success border-success/25",
  "Measured outcome": "bg-success-soft text-success border-success/25",
  "Simulated result": "bg-warning-soft text-warning border-warning/30",
};

function renderTypeIcon(type: EvidenceType): ReactNode {
  switch (type) {
    case "Observed fact":
      return <Database size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "Client statement":
      return <MessageSquareQuote size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "Hypothesis":
      return <HelpCircle size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "AI recommendation":
      return <Sparkles size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "Approved action":
      return <CheckCircle2 size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "Measured outcome":
      return <BarChart3 size={12} strokeWidth={1.75} aria-hidden="true" />;
    case "Simulated result":
      return <FlaskConical size={12} strokeWidth={1.75} aria-hidden="true" />;
  }
}

export function TypeLabel({ type, className = "" }: TypeLabelProps) {
  return (
    <span
      data-evidence-type={type}
      className={[
        "inline-flex items-center gap-1.5 rounded-control border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] whitespace-nowrap",
        TYPE_STYLES[type],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {renderTypeIcon(type)}
      <span>{type}</span>
    </span>
  );
}
