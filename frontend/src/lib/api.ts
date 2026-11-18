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

export interface ProblemBrief {
  id: number;
  engagement_id: number;
  sections: Record<string, unknown>;
  source: "ai_draft" | "edited";
  updated_at: string;
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
