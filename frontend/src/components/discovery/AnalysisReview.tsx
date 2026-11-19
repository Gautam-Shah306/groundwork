import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  Quote,
} from "lucide-react";
import { Button, Card, Eyebrow, StatusPill, TypeLabel } from "../ui";
import type { DiscoveryAnalysis } from "../../lib/api";

export interface AnalysisReviewProps {
  analysis: DiscoveryAnalysis;
  onApply: (confirmReplace: boolean) => Promise<void>;
  onDiscard: () => void;
  isApplying: boolean;
  hasExistingEdits?: boolean;
}

function renderFlagBadge(flag: string) {
  switch (flag) {
    case "quote_not_found":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300"
        >
          <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
          Quote not found in notes
        </span>
      );
    case "quote_missing":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200"
        >
          Quote missing
        </span>
      );
    case "number_not_in_notes":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300"
        >
          <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
          Number not in notes
        </span>
      );
    case "not_hedged":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300"
        >
          <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
          Not hedged
        </span>
      );
    case "causal_wording":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300"
        >
          <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
          Wording implies a cause
        </span>
      );
    case "type_downgraded":
      return (
        <span
          key={flag}
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200"
        >
          <Info className="w-2.5 h-2.5 text-blue-600" />
          Observed fact downgraded to client statement
        </span>
      );
    default:
      return (
        <span
          key={flag}
          className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200"
        >
          {flag}
        </span>
      );
  }
}

export function AnalysisReview({
  analysis,
  onApply,
  onDiscard,
  isApplying,
  hasExistingEdits = false,
}: AnalysisReviewProps) {
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const draft = analysis.draft;

  if (!draft) {
    return null;
  }

  async function handleApplyClick() {
    if (hasExistingEdits) {
      setShowConfirmModal(true);
    } else {
      await onApply(false);
    }
  }

  async function handleConfirmOverwrite() {
    setShowConfirmModal(false);
    await onApply(true);
  }

  const warnings = analysis.warnings || [];

  return (
    <Card className="p-6 bg-stone-50/50 border-stone-300 flex flex-col gap-6 shadow-sm">
      {/* Header bar */}
      <div className="flex items-start justify-between gap-4 border-b border-stone-200 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Eyebrow>AI Analysis Review</Eyebrow>
            <TypeLabel type="AI recommendation" />
            <StatusPill variant="warning" label="AI-generated draft" />
          </div>
          <h3 className="font-serif text-xl font-medium text-stone-900">
            Proposed Problem Brief
          </h3>
          <p className="text-xs text-stone-500 mt-0.5">
            Generated using {analysis.model || "LLM"} from {analysis.notes_chars.toLocaleString()} characters of interview notes.
            Review source quotes and flags before applying.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="tertiary"
            onClick={onDiscard}
            disabled={isApplying}
          >
            Discard draft
          </Button>
          <Button
            variant="primary"
            onClick={handleApplyClick}
            disabled={isApplying}
          >
            {isApplying ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                Apply to Brief
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Warnings summary banner */}
      {warnings.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900 flex flex-col gap-1.5">
          <div className="font-medium flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <span>{warnings.length} review flag{warnings.length === 1 ? "" : "s"} detected</span>
          </div>
          <p className="text-[11px] text-amber-800">
            Some items did not match verbatim quotes or contained unhedged statements.
            You can still apply this draft and edit it in the brief editor.
          </p>
        </div>
      )}

      {/* Sections breakdown */}
      <div className="flex flex-col gap-5 text-xs text-stone-800">
        {/* Problem Statement */}
        {draft.problem_statement && draft.problem_statement.text && (
          <div className="p-3.5 bg-white border border-stone-200 rounded">
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-stone-900">Problem Statement</span>
              <div className="flex items-center gap-1">
                {draft.problem_statement.flags?.map(renderFlagBadge)}
              </div>
            </div>
            <p className="font-serif text-sm text-stone-900 italic">
              &ldquo;{draft.problem_statement.text}&rdquo;
            </p>
          </div>
        )}

        {/* Context */}
        {draft.context && (
          <div>
            <span className="font-medium text-stone-900 block mb-1">Context</span>
            <p className="text-stone-700 leading-relaxed bg-white p-3 rounded border border-stone-200">
              {draft.context}
            </p>
          </div>
        )}

        {/* Themes */}
        {draft.themes && draft.themes.length > 0 && (
          <div>
            <span className="font-medium text-stone-900 block mb-1.5">Key Themes</span>
            <div className="flex flex-col gap-2">
              {draft.themes.map((t, idx) => (
                <div key={t.id || idx} className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-stone-900">{t.text}</span>
                    <div className="flex items-center gap-1">
                      {t.flags?.map(renderFlagBadge)}
                    </div>
                  </div>
                  {t.source_quote && (
                    <div className="flex items-start gap-1 text-[11px] text-stone-500 italic">
                      <Quote className="w-3 h-3 flex-shrink-0 mt-0.5 text-stone-400" />
                      <span>&ldquo;{t.source_quote}&rdquo;</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Symptoms & Impact side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {draft.symptoms && draft.symptoms.length > 0 && (
            <div>
              <span className="font-medium text-stone-900 block mb-1.5">Symptoms</span>
              <div className="flex flex-col gap-2">
                {draft.symptoms.map((s, idx) => (
                  <div key={s.id || idx} className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1">
                    <div className="flex items-start justify-between gap-2">
                      <span>{s.text}</span>
                      <div className="flex items-center gap-1">
                        {s.flags?.map(renderFlagBadge)}
                      </div>
                    </div>
                    {s.source_quote && (
                      <span className="text-[11px] text-stone-500 italic">&ldquo;{s.source_quote}&rdquo;</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {draft.impact && draft.impact.length > 0 && (
            <div>
              <span className="font-medium text-stone-900 block mb-1.5">Business Impact</span>
              <div className="flex flex-col gap-2">
                {draft.impact.map((im, idx) => (
                  <div key={im.id || idx} className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1">
                    <div className="flex items-start justify-between gap-2">
                      <span>{im.text}</span>
                      <div className="flex items-center gap-1">
                        {im.flags?.map(renderFlagBadge)}
                      </div>
                    </div>
                    {im.source_quote && (
                      <span className="text-[11px] text-stone-500 italic">&ldquo;{im.source_quote}&rdquo;</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Known Facts & Hypotheses */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {draft.known_facts && draft.known_facts.length > 0 && (
            <div>
              <span className="font-medium text-stone-900 block mb-1.5">Known Facts</span>
              <div className="flex flex-col gap-2">
                {draft.known_facts.map((kf, idx) => (
                  <div key={kf.id || idx} className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1">
                    <div className="flex items-start justify-between gap-2">
                      <span>{kf.text}</span>
                      <div className="flex items-center gap-1">
                        <TypeLabel type={kf.type === "observed_fact" ? "Observed fact" : "Client statement"} />
                        {kf.flags?.map(renderFlagBadge)}
                      </div>
                    </div>
                    {kf.source_quote && (
                      <span className="text-[11px] text-stone-500 italic">&ldquo;{kf.source_quote}&rdquo;</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {draft.hypotheses && draft.hypotheses.length > 0 && (
            <div>
              <span className="font-medium text-stone-900 block mb-1.5">Hypotheses</span>
              <div className="flex flex-col gap-2">
                {draft.hypotheses.map((h, idx) => (
                  <div key={h.id || idx} className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1">
                    <div className="flex items-start justify-between gap-2">
                      <span>{h.text}</span>
                      <div className="flex items-center gap-1">
                        <StatusPill variant="warning" label="Needs validation" />
                        {h.flags?.map(renderFlagBadge)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Candidate KPIs */}
        {draft.candidate_kpis && draft.candidate_kpis.length > 0 && (
          <div>
            <span className="font-medium text-stone-900 block mb-1.5">Candidate KPIs</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {draft.candidate_kpis.map((kpi, idx) => (
                <div key={kpi.id || idx} className="p-2.5 bg-white border border-stone-200 rounded">
                  <div className="font-mono text-xs font-semibold text-stone-900">{kpi.metric_id}</div>
                  <div className="text-[11px] text-stone-600 mt-0.5">{kpi.rationale}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Confirmation modal for overwriting edits */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-stone-300 max-w-md w-full p-6 shadow-xl flex flex-col gap-4">
            <div className="flex items-center gap-2 text-amber-700">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <h4 className="font-serif text-lg font-medium text-stone-900">
                Overwrite existing brief edits?
              </h4>
            </div>
            <p className="text-xs text-stone-600 leading-relaxed">
              This engagement's problem brief has manual edits. Applying this AI analysis draft
              will replace the current brief content. A copy of your current brief will be saved
              in version history so you can restore it at any time.
            </p>
            <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
              <Button
                variant="tertiary"
                onClick={() => setShowConfirmModal(false)}
                disabled={isApplying}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmOverwrite}
                disabled={isApplying}
              >
                {isApplying ? "Replacing..." : "Confirm & overwrite"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
