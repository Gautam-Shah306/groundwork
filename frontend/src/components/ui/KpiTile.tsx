import { StatusPill, type StatusPillVariant } from "./StatusPill";

export interface KpiTarget {
  value: string;
  source: string;
}

export interface KpiTileProps {
  name: string;
  value: string | number;
  unit?: string;
  period: string;
  baseline?: string;
  target?: KpiTarget;
  statusLabel?: string;
  statusVariant?: StatusPillVariant;
  className?: string;
}

export function KpiTile({
  name,
  value,
  unit,
  period,
  baseline,
  target,
  statusLabel,
  statusVariant = "neutral",
  className = "",
}: KpiTileProps) {
  const hasSourcedTarget = Boolean(target && target.source.trim().length > 0);

  return (
    <article
      className={[
        "flex flex-col justify-between gap-3 rounded-card border border-border bg-surface p-5",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-[12px] font-semibold text-muted">{name}</h3>
        {statusLabel && (
          <StatusPill variant={statusVariant} label={statusLabel} />
        )}
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="font-display text-[32px] font-normal leading-none text-ink tabular-nums">
          {value}
        </span>
        {unit && (
          <span className="text-[12px] font-medium text-muted">{unit}</span>
        )}
      </div>

      <dl className="space-y-1 border-t border-border pt-3 text-[11px] text-muted">
        <div className="flex items-center justify-between gap-2">
          <dt>Period</dt>
          <dd className="font-medium text-ink tabular-nums">{period}</dd>
        </div>
        {baseline && (
          <div className="flex items-center justify-between gap-2">
            <dt>Baseline</dt>
            <dd className="font-medium text-ink tabular-nums">{baseline}</dd>
          </div>
        )}
        {hasSourcedTarget && target && (
          <div className="flex items-center justify-between gap-2">
            <dt>Target ({target.source})</dt>
            <dd className="font-medium text-ink tabular-nums">{target.value}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}
