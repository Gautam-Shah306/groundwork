export interface HealthPayload {
  status: string;
  version: string;
  llm_configured: boolean;
  database_url_scheme: string;
}

export type EngagementStage = "discover" | "diagnose" | "build" | "measure";

export interface Engagement {
  id: number;
  name: string;
  client_name: string;
  industry: string;
  client_statement: string;
  stage: EngagementStage;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
}

export interface EngagementCreateInput {
  name: string;
  client_name: string;
  industry?: string;
  client_statement?: string;
  stage?: EngagementStage;
  is_synthetic?: boolean;
}

export interface InterviewNote {
  id: number;
  engagement_id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface BriefItem {
  id: string;
  text: string;
  source_quote?: string | null;
  quote_verified?: boolean | null;
  origin?: "ai" | "user" | "confirmed";
  status?: "ai_draft" | "user_edited" | "confirmed";
  flags?: string[];
}

export interface KnownFactItem extends BriefItem {
  type: "client_statement" | "observed_fact";
  source?: string;
}

export interface QuestionItem {
  id: string;
  question: string;
  status: "open" | "asked" | "answered";
  source_finding_id?: string | null;
  answer?: string;
  status_reason?: string;
  flags?: string[];
}

export interface ProblemStatement {
  text: string;
  status?: "ai_draft" | "user_edited" | "confirmed";
  flags?: string[];
}

export interface KpiCandidate {
  id: string;
  metric_id: string;
  rationale: string;
  baseline_value?: number | null;
  status?: "ai_draft" | "user_edited" | "confirmed";
  flags?: string[];
}

export interface BriefSections {
  context?: string;
  themes: BriefItem[];
  stakeholders: BriefItem[];
  workflow_steps: BriefItem[];
  symptoms: BriefItem[];
  impact: BriefItem[];
  known_facts: KnownFactItem[];
  hypotheses: BriefItem[];
  assumptions: BriefItem[];
  unknowns: BriefItem[];
  follow_up_questions: QuestionItem[];
  problem_statement: ProblemStatement;
  candidate_kpis: KpiCandidate[];
  [key: string]: unknown;
}

export interface ProblemBrief {
  id: number;
  engagement_id: number;
  sections: BriefSections;
  source: "ai_draft" | "edited";
  updated_at: string;
}

export interface BriefVersion {
  id: number;
  engagement_id: number;
  sections: BriefSections;
  source: string;
  reason: string;
  saved_at: string;
}

export interface DiscoveryWarning {
  code: string;
  section?: string;
  item_id?: string;
  text?: string;
  source_quote?: string;
  metric_id?: string;
  message: string;
}

export interface DiscoveryAnalysis {
  id: number;
  engagement_id: number;
  note_ids: number[] | null;
  status: "completed" | "failed";
  draft: BriefSections | null;
  warnings: DiscoveryWarning[];
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  model: string;
  usage: { input_tokens?: number; output_tokens?: number; total_tokens?: number } | null;
  notes_chars: number;
  created_at: string;
  applied_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  engagement_id: number | null;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ValidationExampleRef {
  row_id: number;
  ticket_id: string;
}

export interface ValidationCheckReport {
  code: string;
  severity: "warning";
  count: number;
  affects: string[];
  message: string;
  recommended_action: string;
  examples: ValidationExampleRef[];
}

export interface DatasetWarning {
  code: string;
  severity: string;
  count: number;
  message: string;
  columns?: string[];
  assumed_timezone?: string;
}

export interface ValidationReport {
  record_count: number;
  period_start: string | null;
  period_end: string | null;
  distinct_ticket_ids: number;
  distinct_customers: number;
  dataset_warnings: DatasetWarning[];
  checks: ValidationCheckReport[];
  rows_valid_for_all_metrics: number;
  excluded_by_scope: {
    all_metrics: number;
    response_metrics: number;
    resolution_metrics: number;
    triage_metrics: number;
  };
}

export interface DatasetRecord {
  id: number;
  engagement_id: number;
  filename: string;
  is_sample: boolean;
  is_active: boolean;
  uploaded_at: string;
  record_count: number;
  period_start: string | null;
  period_end: string | null;
  validation_report: ValidationReport;
}

export interface TicketFlag {
  code: string;
  affects: string[];
}

export interface TicketRowRecord {
  row_id: number;
  ticket_id: string;
  engagement_id: number;
  dataset_id: number;
  created_at: string | null;
  assigned_at: string | null;
  first_response_at: string | null;
  resolved_at: string | null;
  category: string | null;
  priority: string | null;
  queue: string | null;
  assigned_agent: string | null;
  status: string | null;
  channel: string | null;
  reassignment_count: number;
  customer_id: string | null;
  is_valid: boolean;
  validation_flags: TicketFlag[];
}

export interface DatasetRowsPage {
  dataset_id: number;
  flag: string | null;
  page: number;
  page_size: number;
  total: number;
  items: TicketRowRecord[];
}

export interface DiagnosticsDatasetSummary {
  id: number;
  engagement_id: number;
  filename: string;
  is_sample: boolean;
  is_active: boolean;
  uploaded_at: string;
  record_count: number;
  period_start: string | null;
  period_end: string | null;
}

export interface DiagnosticsKpi {
  metric_id: string;
  name: string;
  value: number | null;
  unit: string;
  period_start: string | null;
  period_end: string | null;
  n: number;
  definition: string;
  scope: string;
  n_excluded: number;
  exclusions: Record<string, number>;
  note?: string | null;
}

export interface MetricResultRecord<T = unknown> {
  metric_id: string;
  title: string;
  definition: string;
  unit: string;
  scope: string;
  n_included: number;
  n_excluded: number;
  exclusions: Record<string, number>;
  params: Record<string, unknown>;
  data: T;
  notes: string[];
  as_of: string | null;
}

export interface FindingEvidenceRef {
  metric_id: string;
  params: Record<string, unknown>;
  label: string;
  value: number | string | null;
  unit: string;
  n: number;
}

export interface ValidationQuestionItem {
  text: string;
  kind: "template_question";
  finding_id: string | null;
}

export interface DiagnosticFinding {
  id: string;
  title: string;
  strength: "strong" | "moderate" | "weak" | "info" | null;
  status: "supported" | "insufficient_data";
  observation: { type: "observed_fact"; text: string };
  hypothesis: { type: "hypothesis"; text: string };
  evidence: FindingEvidenceRef[];
  limitations: string[];
  validation_questions: ValidationQuestionItem[];
}

export interface DiagnosticsResponse {
  dataset: DiagnosticsDatasetSummary;
  as_of: string | null;
  timezone: string;
  scope_summary: {
    total_rows: number;
    rows_valid_for_all_metrics: number;
    excluded_by_scope: {
      all_metrics: number;
      response_metrics: number;
      resolution_metrics: number;
      triage_metrics: number;
    };
  };
  kpis: DiagnosticsKpi[];
  metrics: Record<string, MetricResultRecord>;
  findings: DiagnosticFinding[];
  validation_questions: ValidationQuestionItem[];
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL ?? "";
  return configured.replace(/\/+$/, "");
}

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    if (
      body.detail &&
      typeof body.detail === "object" &&
      !Array.isArray(body.detail) &&
      typeof (body.detail as { message?: unknown }).message === "string"
    ) {
      return (body.detail as { message: string }).message;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0] as { msg?: string };
      if (first?.msg) {
        return first.msg;
      }
    }
  } catch {
    // Fall back to HTTP status message if response body is not JSON.
  }
  return `${fallback} (HTTP ${response.status})`;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthPayload> {
  const response = await fetch(buildApiUrl("/api/health"), {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Health endpoint returned HTTP ${response.status}`);
  }

  return (await response.json()) as HealthPayload;
}

export async function fetchEngagements(signal?: AbortSignal): Promise<Engagement[]> {
  const response = await fetch(buildApiUrl("/api/engagements"), {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load engagements")
    );
  }

  return (await response.json()) as Engagement[];
}

export async function createEngagement(
  input: EngagementCreateInput
): Promise<Engagement> {
  const response = await fetch(buildApiUrl("/api/engagements"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to create engagement")
    );
  }

  return (await response.json()) as Engagement;
}

export async function deleteEngagement(engagementId: number): Promise<void> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}`),
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to delete engagement")
    );
  }
}

export async function fetchBrief(
  engagementId: number,
  signal?: AbortSignal
): Promise<ProblemBrief | null> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/brief`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load problem brief")
    );
  }

  return (await response.json()) as ProblemBrief;
}

export async function fetchActivity(
  engagementId: number,
  limit = 10,
  signal?: AbortSignal
): Promise<AuditLogEntry[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/activity?limit=${limit}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load recent activity")
    );
  }

  return (await response.json()) as AuditLogEntry[];
}

export async function fetchDatasets(
  engagementId: number,
  signal?: AbortSignal
): Promise<DatasetRecord[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/datasets`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load datasets")
    );
  }

  return (await response.json()) as DatasetRecord[];
}

export async function uploadDatasetFile(
  engagementId: number,
  file: File
): Promise<DatasetRecord> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/datasets`),
    {
      method: "POST",
      headers: { Accept: "application/json" },
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to upload CSV dataset")
    );
  }

  return (await response.json()) as DatasetRecord;
}

export async function loadSampleDataset(
  engagementId: number
): Promise<DatasetRecord> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/datasets/sample`),
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load sample dataset")
    );
  }

  return (await response.json()) as DatasetRecord;
}

export async function fetchDatasetRows(
  engagementId: number,
  datasetId: number,
  options: { flag?: string | null; page?: number; pageSize?: number } = {},
  signal?: AbortSignal
): Promise<DatasetRowsPage> {
  const params = new URLSearchParams();
  if (options.flag) {
    params.set("flag", options.flag);
  }
  params.set("page", String(options.page ?? 1));
  params.set("page_size", String(options.pageSize ?? 25));

  const response = await fetch(
    buildApiUrl(
      `/api/engagements/${engagementId}/datasets/${datasetId}/rows?${params.toString()}`
    ),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load flagged ticket rows")
    );
  }

  return (await response.json()) as DatasetRowsPage;
}

export async function deleteDataset(
  engagementId: number,
  datasetId: number
): Promise<void> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/datasets/${datasetId}`),
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to delete dataset")
    );
  }
}

export async function fetchDiagnostics(
  engagementId: number,
  datasetId: number,
  signal?: AbortSignal
): Promise<DiagnosticsResponse> {
  const response = await fetch(
    buildApiUrl(
      `/api/engagements/${engagementId}/datasets/${datasetId}/diagnostics`
    ),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load diagnostics analysis")
    );
  }

  return (await response.json()) as DiagnosticsResponse;
}


export interface AssistantToolError {
  code: string;
  message: string;
}

export interface AssistantToolTraceItem {
  call_id: string;
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
  data: Record<string, unknown> | unknown[] | null;
  error: AssistantToolError | null;
  duration_ms: number;
  truncated?: boolean;
  original_row_count?: number | null;
}

export type AssistantBlockType =
  | "finding"
  | "hypothesis"
  | "recommended_next_step"
  | "clarifying_question"
  | "limitation"
  | "unverified";

export interface AssistantBlock {
  type: AssistantBlockType;
  text: string;
  evidence_call_ids: string[];
}

export interface AssistantWarning {
  block_index: number;
  code:
    | "ungrounded_number"
    | "number_only_in_uncited_call"
    | "unsupported_finding"
    | "causal_wording_in_finding";
  message: string;
  details: Record<string, unknown>;
}

export interface AssistantRunError {
  code: string;
  message: string;
}

export interface AssistantRun {
  id: number;
  engagement_id: number;
  dataset_id: number;
  question: string;
  status: "running" | "completed" | "failed";
  answer_status: "structured" | "unstructured" | "none";
  answer_blocks: AssistantBlock[];
  tool_trace: AssistantToolTraceItem[];
  warnings: AssistantWarning[];
  error: AssistantRunError | null;
  model: string;
  round_trips: number;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface CreateAssistantRunResult {
  run_id: number;
  status: string;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

async function extractStructuredApiError(
  response: Response,
  fallback: string
): Promise<ApiRequestError> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (
      body.detail &&
      typeof body.detail === "object" &&
      !Array.isArray(body.detail)
    ) {
      const d = body.detail as { code?: unknown; message?: unknown };
      const msg =
        typeof d.message === "string" && d.message.trim()
          ? d.message
          : `${fallback} (HTTP ${response.status})`;
      const code = typeof d.code === "string" ? d.code : null;
      return new ApiRequestError(msg, response.status, code);
    }
    if (typeof body.detail === "string" && body.detail.trim()) {
      return new ApiRequestError(body.detail, response.status, null);
    }
  } catch {
    // Fall back when response body is not JSON.
  }
  return new ApiRequestError(
    `${fallback} (HTTP ${response.status})`,
    response.status,
    null
  );
}

export async function startAssistantRun(
  engagementId: number,
  question: string,
  datasetId?: number
): Promise<CreateAssistantRunResult> {
  const payload: { question: string; dataset_id?: number } = { question };
  if (datasetId !== undefined) {
    payload.dataset_id = datasetId;
  }

  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/assistant/runs`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to start investigation"
    );
  }

  return (await response.json()) as CreateAssistantRunResult;
}

export async function fetchAssistantRuns(
  engagementId: number,
  limit = 10,
  signal?: AbortSignal
): Promise<AssistantRun[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/assistant/runs?limit=${limit}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to load previous investigations"
    );
  }

  return (await response.json()) as AssistantRun[];
}

export async function fetchAssistantRun(
  engagementId: number,
  runId: number,
  signal?: AbortSignal
): Promise<AssistantRun> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/assistant/runs/${runId}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to load investigation run"
    );
  }

  return (await response.json()) as AssistantRun;
}

export async function fetchNotes(
  engagementId: number,
  signal?: AbortSignal
): Promise<InterviewNote[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/notes`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load interview notes")
    );
  }

  return (await response.json()) as InterviewNote[];
}

export async function createNote(
  engagementId: number,
  input: { title: string; content: string }
): Promise<InterviewNote> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/notes`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to create interview note")
    );
  }

  return (await response.json()) as InterviewNote;
}

export async function updateNote(
  engagementId: number,
  noteId: number,
  input: { title?: string; content?: string }
): Promise<InterviewNote> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/notes/${noteId}`),
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to update interview note")
    );
  }

  return (await response.json()) as InterviewNote;
}

export async function deleteNote(
  engagementId: number,
  noteId: number
): Promise<void> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/notes/${noteId}`),
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to delete interview note")
    );
  }
}

export async function updateBrief(
  engagementId: number,
  sections: BriefSections,
  source = "edited"
): Promise<ProblemBrief> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/brief`),
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ sections, source }),
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to save problem brief")
    );
  }

  return (await response.json()) as ProblemBrief;
}

export async function fetchBriefVersions(
  engagementId: number,
  signal?: AbortSignal
): Promise<BriefVersion[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/brief/versions`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load brief version history")
    );
  }

  return (await response.json()) as BriefVersion[];
}

export async function restoreBriefVersion(
  engagementId: number,
  versionId: number
): Promise<ProblemBrief> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/brief/versions/${versionId}/restore`),
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to restore brief version")
    );
  }

  return (await response.json()) as ProblemBrief;
}

export async function runDiscoveryAnalysis(
  engagementId: number,
  noteIds?: number[]
): Promise<DiscoveryAnalysis> {
  const payload = noteIds && noteIds.length > 0 ? { note_ids: noteIds } : {};
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/discovery/analyse`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to run discovery analysis"
    );
  }

  return (await response.json()) as DiscoveryAnalysis;
}

export async function fetchDiscoveryAnalyses(
  engagementId: number,
  signal?: AbortSignal
): Promise<DiscoveryAnalysis[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/discovery/analyses`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Unable to load discovery analyses")
    );
  }

  return (await response.json()) as DiscoveryAnalysis[];
}

export async function applyDiscoveryAnalysis(
  engagementId: number,
  analysisId: number,
  confirmReplace = false
): Promise<ProblemBrief> {
  const response = await fetch(
    buildApiUrl(
      `/api/engagements/${engagementId}/discovery/analyses/${analysisId}/apply`
    ),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ confirm_replace: confirmReplace }),
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to apply discovery draft to problem brief"
    );
  }

  return (await response.json()) as ProblemBrief;
}
