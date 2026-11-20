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


export type AllowedChannel = "email" | "chat" | "web_form" | "whatsapp";
export type PriorityLevel = "low" | "medium" | "high";
export type ProposalDecision = "approve" | "reject";

export interface ProposalSignal {
  signal: string;
  source_quote: string;
  quote_verified?: boolean | null;
}

export interface ProposalFlag {
  code: string;
  message: string;
  where: string;
}

export interface PipelineTraceStep {
  call_id: string;
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
  data?: Record<string, unknown> | null;
  error?: { code: string; message: string } | null;
  duration_ms: number;
}

export const ALLOWED_PLACEHOLDERS: readonly string[] = [
  "[CUSTOMER_NAME]",
  "[ORDER_ID]",
  "[TRACKING_STATUS]",
  "[REFUND_AMOUNT]",
  "[DELIVERY_DATE]",
  "[AGENT_NAME]",
] as const;

export interface ProposalFinalValues {
  category: string;
  priority: PriorityLevel;
  queue: string;
  reply_text: string;
  edited_fields?: string[];
}

export interface TriageProposalResponse {
  id: number;
  engagement_id: number;
  ticket_hash?: string | null;
  subject?: string | null;
  body: string;
  channel?: string | null;
  category: string;
  secondary_category?: string | null;
  priority: string;
  queue: string;
  escalation: boolean;
  rule_id?: string | null;
  rule_definition?: string | null;
  signals: ProposalSignal[];
  rationale?: string | null;
  draft_reply: string;
  policy_refs: string[];
  reviewer_note?: string | null;
  flags: ProposalFlag[];
  tool_trace: PipelineTraceStep[];
  model?: string | null;
  usage?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  status: "awaiting_approval" | "approved" | "rejected";
  final_values?: ProposalFinalValues | null;
  decided_by?: string | null;
  decision_reason?: string | null;
  edited: boolean;
  created_at: string;
  decided_at?: string | null;
  allowed_placeholders?: string[];
}

export interface CreateProposalPayload {
  subject?: string | null;
  body: string;
  channel?: AllowedChannel;
}

export interface ProposalCreateResponse {
  proposal: TriageProposalResponse;
  duplicate: boolean;
}

export interface ProposalsListResponse {
  items: TriageProposalResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProposalDecisionPayload {
  decision: ProposalDecision;
  final?: ProposalFinalValues | null;
  reason?: string | null;
}

export interface ProposalDecisionResponse {
  proposal_id: number;
  decision: ProposalDecision;
  status: string;
  edited: boolean;
  edited_fields: string[];
  unresolved_placeholders: string[];
  decided_by: string;
  decided_at: string;
}

export async function createTriageProposal(
  engagementId: number,
  payload: CreateProposalPayload
): Promise<ProposalCreateResponse> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/triage/proposals`),
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
      "Unable to create triage proposal"
    );
  }

  return (await response.json()) as ProposalCreateResponse;
}

export async function fetchTriageProposals(
  engagementId: number,
  options?: { status?: string; page?: number; pageSize?: number },
  signal?: AbortSignal
): Promise<ProposalsListResponse> {
  const params = new URLSearchParams();
  if (options?.status) {
    params.set("status", options.status);
  }
  if (options?.page) {
    params.set("page", String(options.page));
  }
  if (options?.pageSize) {
    params.set("page_size", String(options.pageSize));
  }

  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/triage/proposals${query}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to load triage proposals"
    );
  }

  return (await response.json()) as ProposalsListResponse;
}

export async function fetchTriageProposal(
  engagementId: number,
  proposalId: number,
  signal?: AbortSignal
): Promise<TriageProposalResponse> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/triage/proposals/${proposalId}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to load triage proposal"
    );
  }

  return (await response.json()) as TriageProposalResponse;
}

export async function fetchProposalHistory(
  engagementId: number,
  proposalId: number,
  signal?: AbortSignal
): Promise<AuditLogEntry[]> {
  const response = await fetch(
    buildApiUrl(
      `/api/engagements/${engagementId}/triage/proposals/${proposalId}/history`
    ),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    throw await extractStructuredApiError(
      response,
      "Unable to load proposal action history"
    );
  }

  return (await response.json()) as AuditLogEntry[];
}

export async function recordProposalDecision(
  engagementId: number,
  proposalId: number,
  payload: ProposalDecisionPayload
): Promise<ProposalDecisionResponse> {
  const response = await fetch(
    buildApiUrl(
      `/api/engagements/${engagementId}/triage/proposals/${proposalId}/decision`
    ),
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
      "Unable to record proposal decision"
    );
  }

  return (await response.json()) as ProposalDecisionResponse;
}

export interface EvalRunSummary {
  id: number;
  engagement_id: number;
  model: string;
  sample_size: number;
  status: "running" | "paused" | "completed" | "failed" | "cancelled";
  config: {
    sample_size: number;
    drafts_sample?: number;
    model?: string;
    pacing_seconds?: number;
  };
  progress_done: number;
  progress_total: number;
  config_fingerprint: string;
  started_at: string;
  finished_at?: string | null;
  created_at: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    provider_calls: number;
    estimated_cost_usd?: number | null;
  } | null;
  error?: {
    code: string;
    message: string;
  } | null;
  results?: EvalResults;
}

export interface EvalResults {
  summary: {
    total_tickets: number;
    completed: number;
    failed: number;
    category_accuracy: number;
    category_accuracy_completed: number;
    category_accuracy_wilson: [number, number];
    lenient_category_accuracy: number;
    priority_accuracy: number;
    priority_accuracy_completed?: number;
    queue_accuracy: number;
    reviewer_change_proxy: number;
    missed_high_count?: number;
    category_accuracy_pct: number;
    priority_accuracy_pct: number;
    queue_accuracy_pct: number;
    reviewer_change_proxy_pct: number;
  };
  per_category: Record<
    string,
    {
      support: number;
      predicted_count: number;
      precision: number;
      recall: number;
      f1: number;
    }
  >;
  macro_f1: number;
  category_confusion_matrix: Record<string, Record<string, number>>;
  priority_metrics: {
    priority_accuracy: number;
    priority_accuracy_completed?: number;
    strict_accuracy?: number;
    completed_accuracy?: number;
    confusion_matrix: Record<string, Record<string, number>>;
    under_prioritised: number;
    under_prioritised_share?: number;
    over_prioritised: number;
    over_prioritised_share?: number;
    missed_high: { count: number; rate: number };
    truth_high_no_prediction: { count: number; rate: number };
    priority_errors_by_cause: {
      signals_exact_but_priority_wrong: number;
      signals_missed: number;
      signals_spurious: number;
      signals_both: number;
      model_failure: number;
    };
  };
  signals_metrics: {
    micro_precision: number;
    micro_recall: number;
    micro_f1: number;
    exact_set_match_rate: number;
    per_signal: Record<string, any>;
  };
  slices: Array<{
    name: string;
    count: number;
    category_accuracy: number;
    priority_accuracy: number;
    low_confidence: boolean;
  }>;
  failure_cases: Array<{
    ticket_id: string;
    subject?: string | null;
    body?: string;
    body_snippet?: string;
    language?: string;
    true_category: string;
    predicted_category?: string | null;
    true_priority: string;
    predicted_priority?: string | null;
    true_signals: string[];
    predicted_signals: string[];
    flags?: any[];
    reason: string;
  }>;
  draft_checks?: {
    n?: number;
    count?: number;
    total_flags?: number;
    tickets_with_flags?: number;
    flag_rate?: number;
    flag_counts_by_code?: Record<string, number>;
    counts_by_flag_code?: Record<string, number>;
    unflagged_rate?: number;
    draft_unavailable_count?: number;
    note?: string;
  } | null;
  draft_check?: {
    n?: number;
    count?: number;
    total_flags?: number;
    tickets_with_flags?: number;
    flag_rate?: number;
    counts_by_flag_code?: Record<string, number>;
    flag_counts_by_code?: Record<string, number>;
    unflagged_rate?: number;
    draft_unavailable_count?: number;
    note?: string;
  } | null;
}

export interface EvalItem {
  id: number;
  run_id: number;
  ticket_id: string;
  status: "success" | "error";
  error_code?: string | null;
  predicted_category?: string | null;
  predicted_secondary?: string | null;
  predicted_signals: string[];
  flags: Array<{ code: string; message: string; where: string }>;
  predicted_priority?: string | null;
  rule_id?: string | null;
  predicted_queue?: string | null;
  escalation: boolean;
  usage: Record<string, any>;
  duration_ms: number;
  provider_calls: number;
  draft?: {
    reply: string;
    flags: Array<{ code: string; message: string; where: string }>;
    reviewer_note?: string | null;
    policy_refs?: string[];
  } | null;
  created_at: string;
}

export interface EvalItemsListResponse {
  items: EvalItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateEvalRunPayload {
  sample_size?: number;
  model?: string;
  drafts_sample?: number;
}

export async function fetchEvalRuns(
  engagementId: number,
  signal?: AbortSignal
): Promise<EvalRunSummary[]> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/evaluation/runs`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );
  if (!response.ok) {
    throw await extractStructuredApiError(response, "Unable to load evaluation runs");
  }
  return (await response.json()) as EvalRunSummary[];
}

export async function fetchEvalRun(
  engagementId: number,
  runId: number,
  signal?: AbortSignal
): Promise<EvalRunSummary> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/evaluation/runs/${runId}`),
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    }
  );
  if (!response.ok) {
    throw await extractStructuredApiError(response, "Unable to load evaluation run");
  }
  return (await response.json()) as EvalRunSummary;
}

export interface CreateEvalRunResponse {
  run_id: number;
}

export async function createEvalRun(
  engagementId: number,
  payload: CreateEvalRunPayload
): Promise<CreateEvalRunResponse> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/evaluation/runs`),
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
    throw await extractStructuredApiError(response, "Unable to start evaluation run");
  }
  return (await response.json()) as CreateEvalRunResponse;
}

export async function fetchEvalRunItems(
  engagementId: number,
  runId: number,
  params?: {
    page?: number;
    page_size?: number;
    status?: string;
    failure_only?: boolean;
  },
  signal?: AbortSignal
): Promise<EvalItemsListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.status) query.set("status", params.status);
  if (params?.failure_only) query.set("failure_only", "true");

  const qs = query.toString();
  const url = `/api/engagements/${engagementId}/evaluation/runs/${runId}/items${qs ? `?${qs}` : ""}`;
  const response = await fetch(buildApiUrl(url), {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw await extractStructuredApiError(response, "Unable to load evaluation run items");
  }
  return (await response.json()) as EvalItemsListResponse;
}

export async function resumeEvalRun(
  engagementId: number,
  runId: number
): Promise<EvalRunSummary> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/evaluation/runs/${runId}/resume`),
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  if (!response.ok) {
    throw await extractStructuredApiError(response, "Unable to resume evaluation run");
  }
  return (await response.json()) as EvalRunSummary;
}

export async function cancelEvalRun(
  engagementId: number,
  runId: number
): Promise<EvalRunSummary> {
  const response = await fetch(
    buildApiUrl(`/api/engagements/${engagementId}/evaluation/runs/${runId}/cancel`),
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  if (!response.ok) {
    throw await extractStructuredApiError(response, "Unable to cancel evaluation run");
  }
  return (await response.json()) as EvalRunSummary;
}
