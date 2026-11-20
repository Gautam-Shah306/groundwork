import { useState } from "react";
import { History, RotateCcw, Loader2 } from "lucide-react";
import { Button, Card, Eyebrow, StatusPill } from "../ui";
import type { BriefVersion } from "../../lib/api";

export interface VersionHistoryProps {
  versions: BriefVersion[];
  currentBriefUpdatedAt?: string;
  onRestore: (versionId: number) => Promise<void>;
  isRestoring: boolean;
}

function formatReason(reason: string) {
  switch (reason) {
    case "apply":
      return "Applied from AI draft";
    case "edit":
      return "Manual edit";
    case "restore":
      return "Restored from history";
    default:
      return reason;
  }
}

export function VersionHistory({
  versions,
  onRestore,
  isRestoring,
}: VersionHistoryProps) {
  const [confirmRestoreId, setConfirmRestoreId] = useState<number | null>(null);

  if (!versions || versions.length === 0) {
    return (
      <Card className="p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-stone-500" />
          <Eyebrow>Version History</Eyebrow>
        </div>
        <p className="text-xs text-stone-400">
          No version snapshots saved yet. Versions are created automatically when you save edits or apply AI drafts.
        </p>
      </Card>
    );
  }

  async function handleConfirm(versionId: number) {
    await onRestore(versionId);
    setConfirmRestoreId(null);
  }

  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-stone-700" />
          <Eyebrow>Version History</Eyebrow>
        </div>
        <span className="text-[11px] text-stone-500">
          Last {versions.length} versions
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {versions.map((ver, idx) => {
          const isLatest = idx === 0;
          const isPendingConfirm = confirmRestoreId === ver.id;
          const savedDate = new Date(ver.saved_at);

          return (
            <div
              key={ver.id}
              className={`p-2.5 rounded border text-xs flex flex-col gap-1.5 transition-colors ${
                isLatest
                  ? "border-stone-300 bg-stone-50/60"
                  : "border-stone-200 bg-white"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-stone-900">
                    {formatReason(ver.reason)}
                  </span>
                  {isLatest && (
                    <StatusPill variant="neutral" label="Current" />
                  )}
                  <StatusPill
                    variant={ver.source === "ai_draft" ? "warning" : "neutral"}
                    label={ver.source === "ai_draft" ? "AI draft" : "Manual"}
                  />
                </div>
                {!isLatest && !isPendingConfirm && (
                  <Button
                    variant="tertiary"
                    className="h-6 px-2 text-[11px]"
                    onClick={() => setConfirmRestoreId(ver.id)}
                    disabled={isRestoring}
                  >
                    <RotateCcw className="w-3 h-3 mr-1" />
                    Restore
                  </Button>
                )}
              </div>

              <div className="flex items-center justify-between text-[11px] text-stone-400">
                <span>{savedDate.toLocaleString()}</span>
                {ver.sections?.problem_statement?.text && (
                  <span className="truncate max-w-[180px] italic">
                    &ldquo;{ver.sections.problem_statement.text}&rdquo;
                  </span>
                )}
              </div>

              {/* Confirmation inline dialog */}
              {isPendingConfirm && (
                <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs flex items-center justify-between">
                  <span className="text-amber-900 font-medium">
                    Restore this version?
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="tertiary"
                      className="h-6 px-2 text-[11px]"
                      onClick={() => setConfirmRestoreId(null)}
                      disabled={isRestoring}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="primary"
                      className="h-6 px-2 text-[11px]"
                      onClick={() => handleConfirm(ver.id)}
                      disabled={isRestoring}
                    >
                      {isRestoring ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        "Confirm"
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
