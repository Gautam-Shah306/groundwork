import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Compass,
  Loader2,
} from "lucide-react";
import { AnalysisReview } from "../components/discovery/AnalysisReview";
import { BriefEditor } from "../components/discovery/BriefEditor";
import { FollowUpPanel } from "../components/discovery/FollowUpPanel";
import { NotesPanel } from "../components/discovery/NotesPanel";
import { VersionHistory } from "../components/discovery/VersionHistory";
import {
  Button,
  EmptyState,
  Eyebrow,
  SyntheticDataNotice,
} from "../components/ui";
import { useEngagement } from "../context/EngagementContext";
import {
  ApiRequestError,
  applyDiscoveryAnalysis,
  createNote,
  deleteNote,
  fetchBrief,
  fetchBriefVersions,
  fetchDiscoveryAnalyses,
  fetchHealth,
  fetchNotes,
  restoreBriefVersion,
  runDiscoveryAnalysis,
  updateBrief,
  updateNote,
  type BriefSections,
  type BriefVersion,
  type DiscoveryAnalysis,
  type InterviewNote,
  type ProblemBrief,
  type QuestionItem,
} from "../lib/api";
import { formatRunError } from "../lib/llmErrors";

const EMPTY_SECTIONS: BriefSections = {
  context: "",
  themes: [],
  stakeholders: [],
  workflow_steps: [],
  symptoms: [],
  impact: [],
  known_facts: [],
  hypotheses: [],
  assumptions: [],
  unknowns: [],
  follow_up_questions: [],
  problem_statement: { text: "", status: "ai_draft", flags: [] },
  candidate_kpis: [],
};

export function DiscoveryPage() {
  const {
    activeEngagement,
    loading: engagementLoading,
    error: engagementError,
    refreshEngagements,
  } = useEngagement();

  const [notes, setNotes] = useState<InterviewNote[]>([]);
  const [selectedNoteIds, setSelectedNoteIds] = useState<number[]>([]);
  const [brief, setBrief] = useState<ProblemBrief | null>(null);
  const [versions, setVersions] = useState<BriefVersion[]>([]);
  const [_analyses, setAnalyses] = useState<DiscoveryAnalysis[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState<DiscoveryAnalysis | null>(null);

  const [_pageLoading, setPageLoading] = useState(false);
  const [_pageError, setPageError] = useState<string | null>(null);

  const [isAnalysing, setIsAnalysing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const [llmConfigured, setLlmConfigured] = useState(true);

  // Load health for LLM configuration check
  useEffect(() => {
    fetchHealth()
      .then((h) => setLlmConfigured(h.llm_configured))
      .catch(() => setLlmConfigured(false));
  }, []);

  const loadData = useCallback(async (engagementId: number) => {
    setPageLoading(true);
    setPageError(null);
    try {
      const [notesRes, briefRes, versionsRes, analysesRes] = await Promise.all([
        fetchNotes(engagementId),
        fetchBrief(engagementId),
        fetchBriefVersions(engagementId),
        fetchDiscoveryAnalyses(engagementId),
      ]);
      setNotes(notesRes);
      // Select all notes by default
      setSelectedNoteIds(notesRes.map((n) => n.id));
      setBrief(briefRes);
      setVersions(versionsRes);
      setAnalyses(analysesRes);
      // If there's an unapplied completed analysis, show it for review
      const latestUnapplied = analysesRes.find(
        (a) => a.status === "completed" && !a.applied_at
      );
      if (latestUnapplied) {
        setActiveAnalysis(latestUnapplied);
      } else {
        setActiveAnalysis(null);
      }
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to load discovery data");
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeEngagement) {
      void loadData(activeEngagement.id);
    } else {
      setNotes([]);
      setBrief(null);
      setVersions([]);
      setAnalyses([]);
      setActiveAnalysis(null);
    }
  }, [activeEngagement, loadData]);

  // Note Selection handlers
  function handleToggleSelectNote(noteId: number) {
    setSelectedNoteIds((prev) =>
      prev.includes(noteId) ? prev.filter((id) => id !== noteId) : [...prev, noteId]
    );
  }

  function handleSelectAllNotes() {
    setSelectedNoteIds(notes.map((n) => n.id));
  }

  function handleDeselectAllNotes() {
    setSelectedNoteIds([]);
  }

  // Note CRUD
  async function handleCreateNote(input: { title: string; content: string }) {
    if (!activeEngagement) return;
    const created = await createNote(activeEngagement.id, input);
    setNotes((prev) => [created, ...prev]);
    setSelectedNoteIds((prev) => [...prev, created.id]);
  }

  async function handleUpdateNote(
    noteId: number,
    input: { title: string; content: string }
  ) {
    if (!activeEngagement) return;
    const updated = await updateNote(activeEngagement.id, noteId, input);
    setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
  }

  async function handleDeleteNote(noteId: number) {
    if (!activeEngagement) return;
    await deleteNote(activeEngagement.id, noteId);
    setNotes((prev) => prev.filter((n) => n.id !== noteId));
    setSelectedNoteIds((prev) => prev.filter((id) => id !== noteId));
  }

  // AI Discovery Analysis trigger
  async function handleRunAnalysis() {
    if (!activeEngagement || selectedNoteIds.length === 0) return;
    setIsAnalysing(true);
    setAnalysisError(null);
    try {
      const res = await runDiscoveryAnalysis(activeEngagement.id, selectedNoteIds);
      setActiveAnalysis(res);
      setAnalyses((prev) => [res, ...prev]);
    } catch (err) {
      let code: string | null = null;
      let msg = "Analysis failed";
      if (err instanceof ApiRequestError) {
        code = err.code ?? null;
        msg = err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setAnalysisError(formatRunError(code, msg));
    } finally {
      setIsAnalysing(false);
    }
  }

  // Brief CRUD & Actions
  async function handleSaveBrief(sections: BriefSections) {
    if (!activeEngagement) return;
    setIsSaving(true);
    try {
      const updated = await updateBrief(activeEngagement.id, sections);
      setBrief(updated);
      const v = await fetchBriefVersions(activeEngagement.id);
      setVersions(v);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleApplyAnalysis(confirmReplace: boolean) {
    if (!activeEngagement || !activeAnalysis) return;
    setIsApplying(true);
    try {
      const updated = await applyDiscoveryAnalysis(
        activeEngagement.id,
        activeAnalysis.id,
        confirmReplace
      );
      setBrief(updated);
      setActiveAnalysis(null);
      const [v, a] = await Promise.all([
        fetchBriefVersions(activeEngagement.id),
        fetchDiscoveryAnalyses(activeEngagement.id),
      ]);
      setVersions(v);
      setAnalyses(a);
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "would_overwrite_edits") {
        // Re-throw so modal can prompt
        throw err;
      }
      let code: string | null = null;
      let msg = "Failed to apply analysis";
      if (err instanceof ApiRequestError) {
        code = err.code ?? null;
        msg = err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setAnalysisError(formatRunError(code, msg));
    } finally {
      setIsApplying(false);
    }
  }

  function handleDiscardAnalysis() {
    setActiveAnalysis(null);
  }

  async function handleRestoreVersion(versionId: number) {
    if (!activeEngagement) return;
    setIsRestoring(true);
    try {
      const restored = await restoreBriefVersion(activeEngagement.id, versionId);
      setBrief(restored);
      const v = await fetchBriefVersions(activeEngagement.id);
      setVersions(v);
    } finally {
      setIsRestoring(false);
    }
  }

  function handleQuestionsChange(updatedQuestions: QuestionItem[]) {
    if (!brief) return;
    const updatedSections: BriefSections = {
      ...brief.sections,
      follow_up_questions: updatedQuestions,
    };
    void handleSaveBrief(updatedSections);
  }

  if (engagementLoading) {
    return (
      <div
        role="status"
        aria-busy="true"
        className="flex items-center gap-2 rounded-card border border-border bg-surface p-6 text-[13px] text-muted"
      >
        <Loader2 size={16} strokeWidth={1.75} className="animate-spin text-accent" />
        <span>Loading engagement discovery workspace...</span>
      </div>
    );
  }

  if (engagementError) {
    return (
      <div role="alert" className="rounded-card border border-danger/30 bg-danger-soft p-6">
        <div className="flex items-start gap-3">
          <AlertCircle size={16} className="mt-0.5 shrink-0 text-danger" />
          <div className="space-y-2">
            <h2 className="text-[14px] font-semibold text-danger">Unable to load discovery</h2>
            <p className="text-[13px] text-ink">{engagementError}</p>
            <Button variant="secondary" onClick={() => void refreshEngagements()}>
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!activeEngagement) {
    return (
      <div className="space-y-6">
        <header className="space-y-1.5">
          <Eyebrow>Stage 01 · Discover</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Discovery
          </h1>
        </header>

        <EmptyState
          eyebrow="Stage 01 · Discover"
          title="No engagement selected"
          description="Select or create an engagement in Workspace before adding interview notes and generating a structured problem brief."
          icon={<Compass size={16} strokeWidth={1.75} aria-hidden="true" />}
          action={
            <Link
              to="/engagements"
              className="inline-flex h-9 items-center gap-2 rounded-control border border-ink bg-ink px-3.5 text-[13px] font-medium text-surface hover:bg-ink/90"
            >
              <span>Go to Engagements</span>
              <ArrowRight size={15} strokeWidth={1.75} aria-hidden="true" />
            </Link>
          }
        />
      </div>
    );
  }

  const currentSections = brief?.sections || EMPTY_SECTIONS;
  const hasBriefEdits = brief?.source === "edited";

  return (
    <div className="space-y-6">
      {/* Stage Header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Eyebrow>Stage 01 · Discover</Eyebrow>
            <span className="text-xs text-stone-400">•</span>
            <span className="text-xs font-medium text-stone-600">
              {activeEngagement.name}
            </span>
          </div>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Problem Brief & Discovery
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {activeAnalysis && (
            <Button
              variant="secondary"
              onClick={() => setActiveAnalysis(null)}
            >
              Back to brief editor
            </Button>
          )}
          <Link
            to="/diagnostics"
            className="inline-flex h-9 items-center gap-2 rounded-control border border-border bg-surface px-3.5 text-[13px] font-medium text-ink hover:bg-surface-subtle"
          >
            <span>Proceed to Diagnostics</span>
            <ArrowRight size={15} strokeWidth={1.75} aria-hidden="true" />
          </Link>
        </div>
      </header>

      {activeEngagement.is_synthetic && <SyntheticDataNotice />}

      {analysisError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-xs text-red-800 flex items-start justify-between gap-2">
          <div>
            <div className="font-medium">Discovery Analysis Error</div>
            <div className="mt-0.5">{analysisError}</div>
          </div>
          <button
            type="button"
            className="text-red-500 hover:text-red-900 font-bold px-2 py-0.5"
            onClick={() => setAnalysisError(null)}
          >
            ×
          </button>
        </div>
      )}

      {/* Editorial Document Layout: 2 Columns */}
      <div className="flex flex-col lg:grid lg:grid-cols-12 gap-6 items-start">
        {/* Main Column (8 cols): Brief Editor or Analysis Review */}
        <div className="lg:col-span-8 flex flex-col gap-6 w-full">
          {activeAnalysis ? (
            <AnalysisReview
              analysis={activeAnalysis}
              onApply={handleApplyAnalysis}
              onDiscard={handleDiscardAnalysis}
              isApplying={isApplying}
              hasExistingEdits={hasBriefEdits}
            />
          ) : (
            <BriefEditor
              sections={currentSections}
              source={brief?.source}
              updatedAt={brief?.updated_at}
              onSave={handleSaveBrief}
              isSaving={isSaving}
            />
          )}
        </div>

        {/* Contextual Column (4 cols): Notes, Follow-up Questions, Version History */}
        <div className="lg:col-span-4 flex flex-col gap-6 w-full">
          <NotesPanel
            notes={notes}
            selectedNoteIds={selectedNoteIds}
            onToggleSelectNote={handleToggleSelectNote}
            onSelectAllNotes={handleSelectAllNotes}
            onDeselectAllNotes={handleDeselectAllNotes}
            onCreateNote={handleCreateNote}
            onUpdateNote={handleUpdateNote}
            onDeleteNote={handleDeleteNote}
            onAnalyse={handleRunAnalysis}
            isAnalysing={isAnalysing}
            llmConfigured={llmConfigured}
          />

          <FollowUpPanel
            questions={currentSections.follow_up_questions || []}
            onChange={handleQuestionsChange}
            disabled={isSaving}
          />

          <VersionHistory
            versions={versions}
            currentBriefUpdatedAt={brief?.updated_at}
            onRestore={handleRestoreVersion}
            isRestoring={isRestoring}
          />
        </div>
      </div>
    </div>
  );
}
