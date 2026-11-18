import { useCallback, useEffect, useState } from "react";
import { AlertCircle, BarChart3 } from "lucide-react";
import { Button, EmptyState } from "../ui";
import { fetchDiagnostics, type DiagnosticsResponse } from "../../lib/api";
import { DiagnosticsCharts } from "./DiagnosticsCharts";
import { DiagnosticsKpiGrid } from "./DiagnosticsKpiGrid";
import { FactorComparisonCard } from "./FactorComparisonCard";
import { FindingsSection } from "./FindingsSection";

export interface DiagnosticsAnalysisProps {
  engagementId: number;
  datasetId: number;
}

export function DiagnosticsAnalysis({
  engagementId,
  datasetId,
}: DiagnosticsAnalysisProps) {
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchDiagnostics(engagementId, datasetId, signal);
        setData(result);
      } catch (err) {
        if (!signal?.aborted) {
          setError(
            err instanceof Error && err.message
              ? err.message
              : "Unable to load diagnostics analysis."
          );
        }
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [engagementId, datasetId]
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadAnalysis(controller.signal);
    return () => controller.abort();
  }, [loadAnalysis]);

  if (loading) {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-label="Loading diagnostics analysis"
        data-testid="diagnostics-analysis-skeleton"
        className="space-y-4"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="h-36 animate-pulse rounded-card border border-border bg-surface p-5"
            >
              <div className="h-3 w-32 rounded bg-border" />
              <div className="mt-4 h-7 w-24 rounded bg-border" />
              <div className="mt-6 h-3 w-40 rounded bg-border" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-card border border-danger/30 bg-danger-soft p-5"
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="mt-0.5 shrink-0 text-danger"
          />
          <div className="space-y-2">
            <p className="text-[13px] font-semibold text-danger">
              Unable to load diagnostics analysis
            </p>
            <p className="text-[12px] text-ink">{error}</p>
            <Button variant="secondary" onClick={() => void loadAnalysis()}>
              Retry analysis
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  if (data.scope_summary.rows_valid_for_all_metrics === 0) {
    return (
      <EmptyState
        eyebrow="Analysis unavailable"
        title="No valid rows available for analysis"
        description="Every row in this dataset was flagged for an all-metrics validation error. Inspect the validation summary above and upload a corrected CSV."
        icon={<BarChart3 size={16} strokeWidth={1.75} aria-hidden="true" />}
      />
    );
  }

  const factorMetric = data.metrics.factor_comparison as Parameters<
    typeof FactorComparisonCard
  >[0]["metric"];

  return (
    <div data-testid="diagnostics-analysis" className="space-y-8">
      <DiagnosticsKpiGrid kpis={data.kpis} />

      <DiagnosticsCharts metrics={data.metrics} />

      {factorMetric && <FactorComparisonCard metric={factorMetric} />}

      <FindingsSection
        findings={data.findings}
        metrics={data.metrics}
        validationQuestions={data.validation_questions}
      />
    </div>
  );
}
