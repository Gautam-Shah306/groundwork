import { CheckCircle2, AlertTriangle } from "lucide-react";
import type { ProposalSignal } from "../../lib/api";

export interface SignalListProps {
  signals: ProposalSignal[];
}

export function SignalList({ signals }: SignalListProps) {
  if (!signals || signals.length === 0) {
    return (
      <p className="text-sm text-neutral-500 italic">No specific signals detected in ticket.</p>
    );
  }

  return (
    <ul className="space-y-2">
      {signals.map((sig, idx) => (
        <li
          key={`${sig.signal}-${idx}`}
          className="rounded border border-neutral-200 bg-neutral-50 p-2.5 text-xs text-neutral-800"
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="font-mono font-medium text-neutral-900 bg-neutral-200/60 px-1.5 py-0.5 rounded text-[11px]">
              {sig.signal}
            </span>
            {sig.quote_verified === true && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                <CheckCircle2 size={12} aria-hidden="true" />
                <span>Verified quote</span>
              </span>
            )}
            {sig.quote_verified === false && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                <AlertTriangle size={12} aria-hidden="true" />
                <span>Quote not found in ticket text</span>
              </span>
            )}
          </div>
          {sig.source_quote && (
            <p className="italic text-neutral-600 mt-1 pl-2 border-l-2 border-neutral-300">
              &ldquo;{sig.source_quote}&rdquo;
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
