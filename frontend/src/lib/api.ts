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
