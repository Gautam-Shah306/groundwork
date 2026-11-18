import type { StatusPillVariant } from "../components/ui";
import type { AuditLogEntry, EngagementStage } from "./api";

export const ENGAGEMENT_STAGES: Array<{
  id: EngagementStage;
  label: string;
  description: string;
}> = [
  {
    id: "discover",
    label: "Discover",
    description: "Capture context, interview notes, and a testable problem brief.",
  },
  {
    id: "diagnose",
    label: "Diagnose",
    description: "Validate operational CSV data and calculate deterministic metrics.",
  },
  {
    id: "build",
    label: "Build",
    description: "Prototype ticket triage proposals with human approval controls.",
  },
  {
    id: "measure",
    label: "Measure",
    description: "Compare baselines, sourced targets, and simulated pilot outcomes.",
  },
];

export const STAGE_LABELS: Record<EngagementStage, string> = {
  discover: "Discover",
  diagnose: "Diagnose",
  build: "Build",
  measure: "Measure",
};

export const STAGE_PILL_VARIANTS: Record<EngagementStage, StatusPillVariant> = {
  discover: "info",
  diagnose: "warning",
  build: "neutral",
  measure: "success",
};

export const RECOMMENDED_NEXT_STEPS: Record<EngagementStage, string[]> = {
  discover: [
    "Review intake interview transcripts and separate client statements from confirmed facts.",
    "List open operational questions and unknowns before requesting a ticket export.",
    "Draft a concise, testable problem statement in the Discovery workspace.",
  ],
  diagnose: [
    "Upload a synthetic support-ticket CSV and review any data-quality warnings.",
    "Inspect deterministic first-response, resolution, backlog, and reassignment metrics.",
    "Document candidate bottlenecks and hypotheses that still require client validation.",
  ],
  build: [
    "Test the support triage workflow on representative incoming tickets.",
    "Review policy-grounded draft replies and verify bracketed placeholders for unknown facts.",
    "Approve, edit, or reject proposals so every decision is captured in the audit log.",
  ],
  measure: [
    "Confirm KPI baselines, definitions, and sourced targets before evaluating results.",
    "Review simulated pilot comparisons alongside sample sizes and confounding factors.",
    "Prepare an outcome review recommending whether to continue, modify, expand, or stop.",
  ],
};

export function formatShortDate(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) {
    return isoTimestamp;
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatCurrentDate(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(now);
}

export function getGreeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour < 12) {
    return "Good morning";
  }
  if (hour < 18) {
    return "Good afternoon";
  }
  return "Good evening";
}

export function formatRelativeTime(
  isoTimestamp: string,
  nowMs: number = Date.now()
): string {
  const parsed = new Date(isoTimestamp).getTime();
  if (Number.isNaN(parsed)) {
    return isoTimestamp;
  }

  const diffSeconds = Math.max(0, Math.floor((nowMs - parsed) / 1000));
  if (diffSeconds < 60) {
    return "Just now";
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) {
    return `${diffDays}d ago`;
  }
  return formatShortDate(isoTimestamp);
}

export function formatAuditSentence(entry: AuditLogEntry): string {
  const verbMap: Record<string, string> = {
    create: "created",
    update: "updated",
    delete: "deleted",
    approve: "approved",
    reject: "rejected",
  };
  const verb = verbMap[entry.action] ?? entry.action;

  const entityLabelMap: Record<string, string> = {
    engagement: "engagement",
    note: "interview note",
    brief: "problem brief",
    dataset: "dataset",
    proposal: "triage proposal",
  };
  const entityLabel = entityLabelMap[entry.entity_type] ?? entry.entity_type;

  const detailName =
    typeof entry.details?.name === "string" && entry.details.name.trim()
      ? entry.details.name.trim()
      : typeof entry.details?.title === "string" && entry.details.title.trim()
        ? entry.details.title.trim()
        : null;

  if (detailName) {
    return `${entry.actor} ${verb} ${entityLabel} "${detailName}"`;
  }
  return `${entry.actor} ${verb} ${entityLabel} #${entry.entity_id}`;
}
