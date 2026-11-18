import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { Eyebrow } from "./Eyebrow";

export interface EmptyStateProps {
  title: string;
  description: string;
  eyebrow?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  eyebrow,
  icon,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={[
        "flex flex-col items-start gap-3 rounded-card border border-border bg-surface p-8",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-surface-subtle text-muted">
        {icon ?? <Inbox size={16} strokeWidth={1.75} aria-hidden="true" />}
      </div>
      <div className="max-w-xl space-y-1.5">
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h2 className="text-[14px] font-semibold text-ink">{title}</h2>
        <p className="text-[13px] leading-relaxed text-muted">{description}</p>
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
