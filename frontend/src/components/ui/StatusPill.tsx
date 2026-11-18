import type { ReactNode } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Info,
} from "lucide-react";

export type StatusPillVariant = "neutral" | "info" | "success" | "warning" | "danger";

export interface StatusPillProps {
  variant?: StatusPillVariant;
  label: string;
  icon?: ReactNode;
  className?: string;
}

const VARIANT_STYLES: Record<StatusPillVariant, string> = {
  neutral: "bg-surface-subtle text-muted border-border",
  info: "bg-info-soft text-info border-info/20",
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/25",
  danger: "bg-danger-soft text-danger border-danger/25",
};

function defaultIcon(variant: StatusPillVariant): ReactNode {
  switch (variant) {
    case "success":
      return <CheckCircle2 size={13} strokeWidth={1.75} aria-hidden="true" />;
    case "warning":
      return <AlertTriangle size={13} strokeWidth={1.75} aria-hidden="true" />;
    case "danger":
      return <AlertCircle size={13} strokeWidth={1.75} aria-hidden="true" />;
    case "info":
      return <Info size={13} strokeWidth={1.75} aria-hidden="true" />;
    case "neutral":
    default:
      return <Circle size={12} strokeWidth={1.75} aria-hidden="true" />;
  }
}

export function StatusPill({
  variant = "neutral",
  label,
  icon,
  className = "",
}: StatusPillProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-0.5 text-[11px] font-semibold leading-tight whitespace-nowrap",
        VARIANT_STYLES[variant],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className="inline-flex shrink-0" aria-hidden="true">
        {icon ?? defaultIcon(variant)}
      </span>
      <span>{label}</span>
    </span>
  );
}
