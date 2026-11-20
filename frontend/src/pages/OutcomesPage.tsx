import { useCallback, useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import { useEngagement } from "../context/EngagementContext";
import { NAV_ITEMS } from "../lib/navigation";
import {
  EmptyState,
  Eyebrow,
  SyntheticDataNotice,
} from "../components/ui";
import {
  ObjectiveSection,
  KpiTable,
  InterventionsTable,
  SimulationSection,
  ComparisonChart,
  ReviewSection,
} from "../components/outcomes";
import {
  confirmOutcomeReview,
  createIntervention,
  createKpi,
  deleteIntervention,
  deleteKpi,
  draftOutcomeReview,
  fetchBrief,
  fetchDatasets,
  fetchHealth,
  getInterventions,
  getKpiCatalogue,
  getKpis,
  getOutcomeReview,
  getSimulations,
  recomputeKpiBaseline,
  runSimulation,
  updateIntervention,
  updateOutcomeReview,
  type DatasetRecord,
  type Intervention,
  type InterventionCreateInput,
  type InterventionUpdateInput,
  type Kpi,
  type KpiCatalogueItem,
  type KpiCreateInput,
  type OutcomeReview,
  type OutcomeReviewConfirmInput,
  type OutcomeReviewSections,
  type SimulationParameters,
  type SimulationResult,
} from "../lib/api";

export function OutcomesPage() {
  const { activeEngagement } = useEngagement();
  const engagementId = activeEngagement?.id;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [llmConfigured, setLlmConfigured] = useState(false);

  // Data states
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [problemStatement, setProblemStatement] = useState<string | null>(null);
  const [objectiveText, setObjectiveText] = useState<string>("");
  const [catalogue, setCatalogue] = useState<KpiCatalogueItem[]>([]);
  const [kpis, setKpis] = useState<Kpi[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [simulations, setSimulations] = useState<SimulationResult[]>([]);
  const [review, setReview] = useState<OutcomeReview | null>(null);

  const hasActiveDataset = datasets.length > 0;

  const loadData = useCallback(async () => {
    if (!engagementId) return;
    setLoading(true);
    setError(null);
    try {
      const [health, cat, kpiList, interList, simList, rev, brief, dsets] = await Promise.all([
        fetchHealth().catch(() => ({ llm_configured: false })),
        getKpiCatalogue(engagementId).catch(() => []),
        getKpis(engagementId).catch(() => []),
        getInterventions(engagementId).catch(() => []),
        getSimulations(engagementId).catch(() => []),
        getOutcomeReview(engagementId).catch(() => null),
        fetchBrief(engagementId).catch(() => null),
        fetchDatasets(engagementId).catch(() => []),
      ]);

      setLlmConfigured(health.llm_configured);
      setCatalogue(cat);
      setKpis(kpiList);
      setInterventions(interList);
      setSimulations(simList);
      setReview(rev);
      setDatasets(dsets);

      if (brief?.sections?.problem_statement) {
        const ps = brief.sections.problem_statement;
        if (typeof ps === "object" && ps !== null) {
          setProblemStatement((ps as { statement?: string; text?: string }).statement || (ps as { text?: string }).text || null);
        } else if (typeof ps === "string") {
          setProblemStatement(ps);
        }
      }

      if (rev?.sections?.objective) {
        setObjectiveText(rev.sections.objective);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load outcomes data");
    } finally {
      setLoading(false);
    }
  }, [engagementId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Actions
  const handleAddKpi = async (input: KpiCreateInput) => {
    if (!engagementId) return;
    const created = await createKpi(engagementId, input);
    setKpis((prev) => [...prev, created]);
  };

  const handleDeleteKpi = async (id: number) => {
    if (!engagementId) return;
    await deleteKpi(engagementId, id);
    setKpis((prev) => prev.filter((k) => k.id !== id));
  };

  const handleRecomputeBaseline = async (id: number) => {
    if (!engagementId) return;
    const updated = await recomputeKpiBaseline(engagementId, id);
    setKpis((prev) => prev.map((k) => (k.id === id ? updated : k)));
  };

  const handleAddIntervention = async (input: InterventionCreateInput) => {
    if (!engagementId) return;
    const created = await createIntervention(engagementId, input);
    setInterventions((prev) => [...prev, created]);
  };

  const handleUpdateIntervention = async (id: number, input: InterventionUpdateInput) => {
    if (!engagementId) return;
    const updated = await updateIntervention(engagementId, id, input);
    setInterventions((prev) => prev.map((item) => (item.id === id ? updated : item)));
  };

  const handleDeleteIntervention = async (id: number) => {
    if (!engagementId) return;
    await deleteIntervention(engagementId, id);
    setInterventions((prev) => prev.filter((item) => item.id !== id));
  };

  const handleRunSimulation = async (params: SimulationParameters) => {
    if (!engagementId) return;
    const res = await runSimulation(engagementId, params);
    setSimulations((prev) => [res, ...prev]);
  };

  const handleDraftReview = async (payload?: { objective_text?: string; confirm_replace?: boolean }) => {
    if (!engagementId) return;
    const drafted = await draftOutcomeReview(engagementId, payload);
    setReview(drafted);
  };

  const handleUpdateReview = async (payload: { sections: OutcomeReviewSections }) => {
    if (!engagementId) return;
    const updated = await updateOutcomeReview(engagementId, payload);
    setReview(updated);
  };

  const handleConfirmReview = async (payload: OutcomeReviewConfirmInput) => {
    if (!engagementId) return;
    const confirmed = await confirmOutcomeReview(engagementId, payload);
    setReview(confirmed);
  };

  if (!activeEngagement) {
    const navItem = NAV_ITEMS.find((i) => i.id === "outcomes");
    return (
      <div className="space-y-6">
        <header className="space-y-1.5">
          <Eyebrow>{navItem?.eyebrow ?? "Stage 04 · Measure"}</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Outcomes
          </h1>
        </header>
        <EmptyState
          eyebrow="Synthetic workspace"
          title={navItem?.emptyTitle ?? "No outcome comparison recorded"}
          description={navItem?.emptyDescription ?? "Define KPI baselines, sourced targets, and clearly labelled simulated pilot comparisons to evaluate whether an intervention worked."}
          icon={<TrendingUp size={16} strokeWidth={1.75} aria-hidden="true" />}
        />
      </div>
    );
  }

  const primaryKpi = kpis.find((k) => k.is_primary) || kpis[0] || null;
  const latestSim = simulations[0] || null;

  return (
    <div className="space-y-6 max-w-6xl pb-16">
      <header className="space-y-1.5">
        <Eyebrow>Stage 04 · Measure</Eyebrow>
        <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-2">
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Outcomes
          </h1>
          <SyntheticDataNotice />
        </div>
      </header>

      {error && (
        <div className="p-3 bg-error-soft text-error border border-error/30 rounded-control text-xs">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-muted text-sm border border-dashed border-border rounded-panel">
          Loading outcomes framework...
        </div>
      ) : (
        <div className="space-y-6">
          <ObjectiveSection
            problemStatement={problemStatement}
            objective={objectiveText}
            onObjectiveChange={setObjectiveText}
            disabled={review?.status === "confirmed"}
          />

          <KpiTable
            kpis={kpis}
            catalogue={catalogue}
            hasActiveDataset={hasActiveDataset}
            onAddKpi={handleAddKpi}
            onDeleteKpi={handleDeleteKpi}
            onRecomputeBaseline={handleRecomputeBaseline}
            loading={loading}
          />

          <InterventionsTable
            interventions={interventions}
            onAddIntervention={handleAddIntervention}
            onUpdateIntervention={handleUpdateIntervention}
            onDeleteIntervention={handleDeleteIntervention}
            loading={loading}
          />

          <SimulationSection
            latestSimulation={latestSim}
            simulations={simulations}
            hasActiveDataset={hasActiveDataset}
            onRunSimulation={handleRunSimulation}
            loading={loading}
          />

          <ComparisonChart
            primaryKpi={primaryKpi}
            simulation={latestSim}
          />

          <ReviewSection
            review={review}
            kpiCount={kpis.length}
            isLlmConfigured={llmConfigured}
            objectiveText={objectiveText}
            onDraftReview={handleDraftReview}
            onUpdateReview={handleUpdateReview}
            onConfirmReview={handleConfirmReview}
            loading={loading}
          />
        </div>
      )}
    </div>
  );
}
