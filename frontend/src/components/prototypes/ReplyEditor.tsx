import { useMemo } from "react";
import { AlertTriangle } from "lucide-react";
import { ALLOWED_PLACEHOLDERS } from "../../lib/api";

export interface ReplyEditorProps {
  reply: string;
  onChange?: (newReply: string) => void;
  readOnly?: boolean;
  allowedPlaceholders?: readonly string[];
}

const PLACEHOLDER_REGEX = /\[[A-Za-z0-9_]+\]/g;

export function ReplyEditor({
  reply,
  onChange,
  readOnly = false,
  allowedPlaceholders = ALLOWED_PLACEHOLDERS,
}: ReplyEditorProps) {
  const { validPlaceholders, unknownPlaceholders } = useMemo(() => {
    const matches = reply.match(PLACEHOLDER_REGEX);
    const unique = matches ? Array.from(new Set(matches)) : [];
    const valid: string[] = [];
    const unknown: string[] = [];
    for (const token of unique) {
      if ((allowedPlaceholders as readonly string[]).includes(token)) {
        valid.push(token);
      } else {
        unknown.push(token);
      }
    }
    return { validPlaceholders: valid, unknownPlaceholders: unknown };
  }, [reply, allowedPlaceholders]);

  const charCount = reply.length;
  const isOverLimit = charCount > 2000;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <label htmlFor="triage-reply-editor" className="font-medium text-neutral-700">
          Draft Response {readOnly ? "(AI Proposal)" : "(Editable)"}
        </label>
        <span
          className={`font-mono text-[11px] ${
            isOverLimit ? "text-rose-600 font-semibold" : "text-neutral-500"
          }`}
        >
          {charCount} / 2000
        </span>
      </div>

      <textarea
        id="triage-reply-editor"
        rows={6}
        value={reply}
        readOnly={readOnly}
        onChange={(e) => onChange && onChange(e.target.value)}
        placeholder="Enter or edit customer reply draft..."
        className={`w-full rounded border p-2.5 text-xs text-neutral-800 leading-relaxed font-sans focus:outline-none focus:ring-1 focus:ring-neutral-400 ${
          readOnly
            ? "bg-neutral-50 border-neutral-200 cursor-default"
            : "bg-white border-neutral-300"
        } ${isOverLimit ? "border-rose-400 ring-rose-400" : ""}`}
      />

      {validPlaceholders.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50/70 p-2 text-xs text-amber-800 flex items-start gap-2">
          <AlertTriangle size={14} className="text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="space-y-1">
            <span className="font-semibold block">
              {validPlaceholders.length} unresolved placeholder{validPlaceholders.length > 1 ? "s" : ""} detected:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {validPlaceholders.map((ph) => (
                <span
                  key={ph}
                  className="font-mono text-[11px] bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded border border-amber-300 font-medium"
                >
                  {ph}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-amber-700 mt-1">
              Replace placeholders with concrete details before sending. (Remember: Groundwork never sends messages directly).
            </p>
          </div>
        </div>
      )}

      {unknownPlaceholders.length > 0 && (
        <div className="rounded border border-rose-200 bg-rose-50/70 p-2 text-xs text-rose-800 flex items-start gap-2">
          <AlertTriangle size={14} className="text-rose-600 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="space-y-1">
            <span className="font-semibold block">
              {unknownPlaceholders.length} unknown placeholder{unknownPlaceholders.length > 1 ? "s" : ""} detected:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {unknownPlaceholders.map((ph) => (
                <span
                  key={ph}
                  className="font-mono text-[11px] bg-rose-100 text-rose-900 px-1.5 py-0.5 rounded border border-rose-300 font-medium"
                >
                  {ph} (unknown)
                </span>
              ))}
            </div>
            <p className="text-[11px] text-rose-700 mt-1">
              Bracketed token is not in the approved placeholder list. Please verify against company policies.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
