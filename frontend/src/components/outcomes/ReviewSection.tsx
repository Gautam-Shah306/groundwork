import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileCheck2,
  Lock,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import type {
  OutcomeReview,
  OutcomeReviewConfirmInput,
  OutcomeReviewSections,
} from "../../lib/api";
import { Button, Card, Eyebrow, StatusPill } from "../ui";

export interface ReviewSectionProps {
  review: OutcomeReview | null;
  kpiCount: number;
  isLlmConfigured: boolean;
  objectiveText: string;
  onDraftReview: (payload?: { objective_text?: string; confirm_replace?: boolean }) => Promise<void>;
  onUpdateReview: (payload: { sections: OutcomeReviewSections }) => Promise<void>;
  onConfirmReview: (payload: OutcomeReviewConfirmInput) => Promise<void>;
  loading?: boolean;
}

export function ReviewSection({
  review,
  kpiCount,
  isLlmConfigured,
  objectiveText,
  onDraftReview,
  onUpdateReview,
  onConfirmReview,
  loading = false,
}: ReviewSectionProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedSections, setEditedSections] = useState<OutcomeReviewSections>(
    review?.sections || {}
  );
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmRec, setConfirmRec] = useState<"continue" | "iterate" | "pivot" | "stop">(
    review?.final_recommendation || review?.sections?.recommendation?.value || "continue"
  );
  const [acknowledged, setAcknowledged] = useState(review?.acknowledged_simulated || false);
  const [error, setError] = useState<string | null>(null);

  const isConfirmed = review?.status === "confirmed";

  const handleStartDraft = async (confirmReplace: boolean = false) => {
    setError(null);
    try {
      await onDraftReview({
        objective_text: objectiveText,
        confirm_replace: confirmReplace,
      });
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to draft review");
    }
  };

  const handleSaveEdit = async () => {
    setError(null);
    try {
      await onUpdateReview({ sections: editedSections });
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update review");
    }
  };

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!acknowledged) {
      setError("You must acknowledge that simulated results are not empirical evidence.");
      return;
    }
    setError(null);
    try {
      await onConfirmReview({
        final_recommendation: confirmRec,
        acknowledged_simulated: true,
      });
      setIsConfirming(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to confirm review");
    }
  };

  return (
    <Card className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
        <div>
          <Eyebrow>Executive Synthesis</Eyebrow>
          <div className="flex items-center gap-2">
            <h2 className="font-display text-lg text-ink font-medium">Outcome Review & Operator Decision</h2>
            {review && (
              <StatusPill
                variant={isConfirmed ? "success" : "neutral"}
                label={isConfirmed ? "Confirmed" : "Draft"}
              />
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!review ? (
            <Button
              onClick={() => handleStartDraft(false)}
              disabled={loading || !isLlmConfigured || kpiCount === 0}
              className="gap-1.5"
            >
              <Sparkles size={14} /> AI Draft Outcome Review
            </Button>
          ) : (
            <>
              {!isConfirmed && !isEditing && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setEditedSections(review.sections || {});
                    setIsEditing(true);
                  }}
                  disabled={loading}
                >
                  Edit Review
                </Button>
              )}

              {isEditing && (
                <div className="flex items-center gap-2">
                  <Button variant="secondary" onClick={() => setIsEditing(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleSaveEdit} disabled={loading}>
                    Save Changes
                  </Button>
                </div>
              )}

              {!isConfirmed && !isEditing && !isConfirming && (
                <Button
                  onClick={() => setIsConfirming(true)}
                  disabled={loading}
                  className="gap-1.5"
                >
                  <FileCheck2 size={14} /> Confirm & Approve Review
                </Button>
              )}

              {!isEditing && (
                <Button
                  variant="tertiary"
                  onClick={() => handleStartDraft(true)}
                  disabled={loading || !isLlmConfigured}
                  title="Re-draft with AI"
                  className="gap-1"
                >
                  <RotateCcw size={13} /> Re-draft
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {!isLlmConfigured && (
        <div className="p-3 bg-surface-subtle border border-border rounded-control text-xs text-muted">
          LLM provider is not configured. Set <code className="text-ink">LLM_PROVIDER</code> and <code className="text-ink">LLM_API_KEY</code> in <code className="text-ink">.env</code> to generate automated outcome review drafts.
        </div>
      )}

      {kpiCount === 0 && (
        <div className="p-3 bg-warning-soft border border-warning/30 rounded-control text-xs text-warning">
          At least one KPI must be configured before generating an outcome review.
        </div>
      )}

      {error && (
        <div className="p-3 bg-error-soft text-error border border-error/30 rounded-control text-xs">
          {error}
        </div>
      )}

      {/* Confirmation Banner */}
      {isConfirmed && (
        <div className="rounded-control bg-success-soft/70 border border-success/30 p-3.5 flex items-start gap-3">
          <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <div className="font-semibold text-success flex items-center gap-2">
              <span>Review Confirmed by Human Operator</span>
              <span className="font-mono text-[10px] text-muted">
                {new Date(review.confirmed_at!).toLocaleString()}
              </span>
            </div>
            <p className="text-ink">
              Final Decision:{" "}
              <strong className="uppercase font-mono tracking-wider text-success">
                {review.final_recommendation}
              </strong>
            </p>
            <p className="text-muted text-[11px]">
              Note: Editing any section will automatically revoke confirmation and reset status to draft.
            </p>
          </div>
        </div>
      )}

      {/* Confirmation Form */}
      {isConfirming && !isConfirmed && (
        <form
          onSubmit={handleConfirm}
          className="rounded-panel border-2 border-accent/40 bg-accent-soft/30 p-4 space-y-3"
        >
          <div className="flex items-center justify-between border-b border-border/40 pb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink flex items-center gap-1.5">
              <Lock size={13} /> Operator Decision Confirmation
            </h3>
            <button
              type="button"
              onClick={() => setIsConfirming(false)}
              className="text-xs text-muted hover:text-ink"
            >
              Cancel
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
                Final Engagement Recommendation
              </label>
              <select
                value={confirmRec}
                onChange={(e) =>
                  setConfirmRec(e.target.value as "continue" | "iterate" | "pivot" | "stop")
                }
                className="w-full text-xs rounded border border-border bg-surface px-2.5 py-1.5 text-ink font-medium"
              >
                <option value="continue">Continue (Proceed to rollout)</option>
                <option value="iterate">Iterate (Refine triage prompts and tooling)</option>
                <option value="pivot">Pivot (Explore alternative operational focus)</option>
                <option value="stop">Stop (Do not deploy changes)</option>
              </select>
            </div>

            <label className="flex items-start gap-2.5 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="mt-0.5 rounded border-border text-accent focus:ring-accent"
              />
              <span className="text-xs text-ink leading-snug">
                I acknowledge that simulated results are mathematical projections under assumed parameters and do not represent measured production outcomes.
              </span>
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" type="button" onClick={() => setIsConfirming(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!acknowledged}>
                Confirm Decision
              </Button>
            </div>
          </div>
        </form>
      )}

      {/* Flags & Warnings */}
      {review?.flags && review.flags.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-warning flex items-center gap-1.5">
            <AlertCircle size={13} /> Automated Quality Flags ({review.flags.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {review.flags.map((flag, i) => (
              <span
                key={i}
                className="text-[11px] px-2 py-0.5 rounded border border-warning/30 bg-warning-soft text-warning font-mono"
              >
                {flag.code}: {flag.message}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Review Content */}
      {review ? (
        <div className="space-y-4">
          {/* Recommendation */}
          <div className="rounded-panel border border-border bg-surface-subtle p-4 space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Proposed Recommendation
            </span>
            <div className="text-sm font-semibold uppercase tracking-wider text-ink font-mono">
              {review.sections.recommendation?.value || "continue"}
            </div>
            <p className="text-xs text-ink leading-relaxed">
              {review.sections.recommendation?.rationale || "No rationale supplied."}
            </p>
          </div>

          {/* Grid of Sections */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-panel border border-border p-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink">
                What Improved
              </h4>
              <ul className="list-disc list-inside space-y-1 text-xs text-ink leading-relaxed">
                {(review.sections.what_improved || []).map((item, i) => (
                  <li key={i}>
                    {typeof item === "string" ? item : item.text}
                    {typeof item === "object" && item.evidence_key && (
                      <span className="ml-1 text-[10px] font-mono text-muted bg-surface-subtle px-1.5 py-0.2 rounded border border-border">
                        {item.evidence_key}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-panel border border-border p-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink">
                What Did Not / Tradeoffs
              </h4>
              <ul className="list-disc list-inside space-y-1 text-xs text-ink leading-relaxed">
                {(review.sections.what_did_not || []).map((item, i) => (
                  <li key={i}>{typeof item === "string" ? item : item.text}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-panel border border-border p-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink">
                Limitations & Risks
              </h4>
              <ul className="list-disc list-inside space-y-1 text-xs text-ink leading-relaxed">
                {(review.sections.limitations || []).map((item, i) => (
                  <li key={i}>{typeof item === "string" ? item : item.text}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-panel border border-border p-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink">
                Recommended Next Steps
              </h4>
              <ul className="list-disc list-inside space-y-1 text-xs text-ink leading-relaxed">
                {(review.sections.next_steps || []).map((item, i) => (
                  <li key={i}>{typeof item === "string" ? item : item.text}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-muted text-sm border border-dashed border-border rounded-panel">
          No outcome review drafted yet. Once KPIs and simulations are ready, draft an executive review for human operator confirmation.
        </div>
      )}
    </Card>
  );
}
