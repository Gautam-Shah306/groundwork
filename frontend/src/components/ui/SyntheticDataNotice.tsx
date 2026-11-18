import { FlaskConical } from "lucide-react";

export interface SyntheticDataNoticeProps {
  message?: string;
  className?: string;
}

export function SyntheticDataNotice({
  message = "All engagements, transcripts, tickets, and outcomes shown in this workspace use synthetic demonstration data and do not represent a real client.",
  className = "",
}: SyntheticDataNoticeProps) {
  return (
    <div
      role="note"
      aria-label="Synthetic demonstration data notice"
      className={[
        "flex items-start gap-2.5 rounded-card border border-warning/30 bg-warning-soft px-4 py-3 text-[12px] text-ink",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <FlaskConical
        size={16}
        strokeWidth={1.75}
        aria-hidden="true"
        className="mt-0.5 shrink-0 text-warning"
      />
      <div className="space-y-0.5">
        <div className="font-semibold text-warning">
          Synthetic demonstration data
        </div>
        <p className="leading-relaxed text-ink">{message}</p>
      </div>
    </div>
  );
}
