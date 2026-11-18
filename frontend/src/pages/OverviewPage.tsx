import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Compass,
  LayoutDashboard,
  Loader2,
} from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  Eyebrow,
  StatusPill,
  SyntheticDataNotice,
  TypeLabel,
} from "../components/ui";
import { useEngagement } from "../context/EngagementContext";
import {
  fetchActivity,
  fetchBrief,
  type AuditLogEntry,
  type ProblemBrief,
} from "../lib/api";
import {
  ENGAGEMENT_STAGES,
  RECOMMENDED_NEXT_STEPS,
  STAGE_LABELS,
  STAGE_PILL_VARIANTS,
  formatAuditSentence,
  formatCurrentDate,
  formatRelativeTime,
  getGreeting,
} from "../lib/format";

export function OverviewPage() {
  const {
    activeEngagement,
    loading: engagementsLoading,
    error: engagementsError,
    refreshEngagements,
  } = useEngagement();

  const [brief, setBrief] = useState<ProblemBrief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);

  const [activity, setActivity] = useState<AuditLogEntry[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeEngagement) {
      setBrief(null);
      setBriefError(null);
      setActivity([]);
      setActivityError(null);
      return;
    }

    const controller = new AbortController();
    const engagementId = activeEngagement.id;

    setBriefLoading(true);
    setBriefError(null);
    fetchBrief(engagementId, controller.signal)
      .then((result) => {
        setBrief(result);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setBriefError(
            err instanceof Error ? err.message : "Unable to load problem brief."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setBriefLoading(false);
        }
      });

    setActivityLoading(true);
    setActivityError(null);
    fetchActivity(engagementId, 10, controller.signal)
      .then((entries) => {
        setActivity(entries);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setActivityError(
            err instanceof Error
              ? err.message
              : "Unable to load recent activity."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setActivityLoading(false);
        }
      });

    return () => controller.abort();
  }, [activeEngagement]);

  if (engagementsLoading) {
    return (
      <div
        role="status"
        aria-busy="true"
        className="flex items-center gap-2 rounded-card border border-border bg-surface p-6 text-[13px] text-muted"
      >
        <Loader2
          size={16}
          strokeWidth={1.75}
          aria-hidden="true"
          className="animate-spin text-accent"
        />
        <span>Loading workspace overview...</span>
      </div>
    );
  }

  if (engagementsError) {
    return (
      <div
        role="alert"
        className="rounded-card border border-danger/30 bg-danger-soft p-6"
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="mt-0.5 shrink-0 text-danger"
          />
          <div className="space-y-2">
            <h2 className="text-[14px] font-semibold text-danger">
              Unable to load overview
            </h2>
            <p className="text-[13px] text-ink">{engagementsError}</p>
            <Button
              variant="secondary"
              onClick={() => void refreshEngagements()}
            >
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
          <Eyebrow>Workspace</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Overview
          </h1>
        </header>

        <EmptyState
          eyebrow="Synthetic workspace"
          title="No active engagement loaded"
          description="Select or seed a synthetic engagement to view the current problem statement, stage progress, key findings, and next actions."
          icon={
            <LayoutDashboard size={16} strokeWidth={1.75} aria-hidden="true" />
          }
          action={
            <Link
              to="/engagements"
              className="inline-flex h-9 items-center gap-2 rounded-control border border-ink bg-ink px-3.5 text-[13px] font-medium text-surface hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              <span>Go to Engagements</span>
              <ArrowRight size={15} strokeWidth={1.75} aria-hidden="true" />
            </Link>
          }
        />
      </div>
    );
  }

  const now = new Date();
  const currentStageIndex = ENGAGEMENT_STAGES.findIndex(
    (item) => item.id === activeEngagement.stage
  );
  const problemStatement =
    typeof brief?.sections?.problem_statement === "string" &&
    brief.sections.problem_statement.trim().length > 0
      ? brief.sections.problem_statement.trim()
      : null;

  const suggestedSteps = RECOMMENDED_NEXT_STEPS[activeEngagement.stage];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <Eyebrow>{formatCurrentDate(now)}</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            {getGreeting(now)}, Demo operator
          </h1>
        </div>
        <Link
          to="/engagements"
          className="inline-flex h-9 items-center gap-2 rounded-control border border-border bg-surface px-3.5 text-[13px] font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <span>Manage engagements</span>
          <ArrowRight size={15} strokeWidth={1.75} aria-hidden="true" />
        </Link>
      </header>

      {activeEngagement.is_synthetic && <SyntheticDataNotice />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Primary column */}
        <div className="space-y-6 lg:col-span-2">
          <Card
            title="Active engagement"
            description="Selected client operational workspace."
            headerAction={
              <StatusPill
                variant={STAGE_PILL_VARIANTS[activeEngagement.stage]}
                label={STAGE_LABELS[activeEngagement.stage]}
              />
            }
          >
            <div className="space-y-4">
              <div>
                <h3 className="text-[16px] font-semibold text-ink">
                  {activeEngagement.name}
                </h3>
                <p className="mt-0.5 text-[12px] text-muted">
                  {activeEngagement.client_name}
                  {activeEngagement.industry
                    ? ` · ${activeEngagement.industry}`
                    : ""}
                </p>
              </div>

              {activeEngagement.client_statement && (
                <div className="space-y-2 rounded-control border border-border bg-surface-subtle p-4">
                  <TypeLabel type="Client statement" />
                  <p className="text-[13px] leading-relaxed text-ink">
                    &ldquo;{activeEngagement.client_statement}&rdquo;
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card
            title="Current problem statement"
            description="Testable problem statement from the Discovery problem brief."
            headerAction={
              brief && problemStatement ? (
                <StatusPill
                  variant="info"
                  label={brief.source === "ai_draft" ? "AI draft" : "Edited brief"}
                />
              ) : undefined
            }
          >
            {briefLoading ? (
              <div
                role="status"
                aria-busy="true"
                className="flex items-center gap-2 text-[13px] text-muted"
              >
                <Loader2
                  size={15}
                  strokeWidth={1.75}
                  aria-hidden="true"
                  className="animate-spin text-accent"
                />
                <span>Loading problem brief...</span>
              </div>
            ) : briefError ? (
              <div
                role="alert"
                className="rounded-control border border-danger/30 bg-danger-soft p-3 text-[12px] text-danger"
              >
                {briefError}
              </div>
            ) : problemStatement ? (
              <div className="space-y-3">
                <p className="text-[14px] leading-relaxed text-ink">
                  {problemStatement}
                </p>
                <Link
                  to="/discovery"
                  className="inline-flex items-center gap-1.5 text-[12px] font-medium text-accent hover:underline"
                >
                  <span>Edit in Discovery</span>
                  <ArrowRight size={14} strokeWidth={1.75} aria-hidden="true" />
                </Link>
              </div>
            ) : (
              <EmptyState
                eyebrow="Stage 01 · Discover"
                title="No problem statement drafted yet"
                description="Review the intake transcript and structure a testable problem statement in Discovery before moving to diagnostics."
                icon={
                  <Compass size={16} strokeWidth={1.75} aria-hidden="true" />
                }
                action={
                  <Link
                    to="/discovery"
                    className="inline-flex h-9 items-center gap-2 rounded-control border border-border bg-surface px-3.5 text-[13px] font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    <span>Open Discovery</span>
                    <ArrowRight
                      size={15}
                      strokeWidth={1.75}
                      aria-hidden="true"
                    />
                  </Link>
                }
                className="border-0 bg-surface-subtle p-5"
              />
            )}
          </Card>

          <Card
            title="Stage progress"
            description="Four-stage operational workflow from problem framing through outcome measurement."
          >
            <ol
              aria-label="Engagement stage progress"
              className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
            >
              {ENGAGEMENT_STAGES.map((stageItem, index) => {
                const isCurrent = stageItem.id === activeEngagement.stage;
                const isCompleted = index < currentStageIndex;
                const stepStateText = isCurrent
                  ? "Current stage"
                  : isCompleted
                    ? "Completed"
                    : "Upcoming";

                return (
                  <li
                    key={stageItem.id}
                    aria-current={isCurrent ? "step" : undefined}
                    className={[
                      "rounded-control border p-3.5",
                      isCurrent
                        ? "border-accent bg-accent-soft"
                        : "border-border bg-surface-subtle",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-sans text-[10px] font-bold uppercase tracking-[0.08em] text-muted tabular-nums">
                        0{index + 1}
                      </span>
                      <span
                        className={
                          isCurrent
                            ? "text-[10px] font-semibold uppercase tracking-[0.06em] text-accent"
                            : "text-[10px] font-medium uppercase tracking-[0.06em] text-muted"
                        }
                      >
                        {stepStateText}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[13px] font-semibold text-ink">
                      {stageItem.label}
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-muted">
                      {stageItem.description}
                    </p>
                  </li>
                );
              })}
            </ol>
          </Card>
        </div>

        {/* Contextual column */}
        <div className="space-y-6">
          <Card
            title="Recommended next steps"
            description={`Suggested operator workflow actions for the ${STAGE_LABELS[activeEngagement.stage]} stage.`}
          >
            <ul className="space-y-3">
              {suggestedSteps.map((step, index) => (
                <li
                  key={step}
                  className="flex items-start gap-2.5 text-[12px] leading-relaxed text-ink"
                >
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-control border border-border bg-surface-subtle text-[10px] font-semibold text-muted tabular-nums">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card
            title="Recent activity"
            description="Latest recorded audit events for this engagement."
          >
            {activityLoading ? (
              <div
                role="status"
                aria-busy="true"
                className="flex items-center gap-2 text-[12px] text-muted"
              >
                <Loader2
                  size={15}
                  strokeWidth={1.75}
                  aria-hidden="true"
                  className="animate-spin text-accent"
                />
                <span>Loading recent activity...</span>
              </div>
            ) : activityError ? (
              <div
                role="alert"
                className="rounded-control border border-danger/30 bg-danger-soft p-3 text-[12px] text-danger"
              >
                {activityError}
              </div>
            ) : activity.length === 0 ? (
              <p className="text-[12px] text-muted">
                No audit events recorded for this engagement yet.
              </p>
            ) : (
              <ol aria-label="Recent activity" className="divide-y divide-border">
                {activity.map((entry) => (
                  <li key={entry.id} className="py-2.5 first:pt-0 last:pb-0">
                    <p className="text-[12px] leading-snug text-ink">
                      {formatAuditSentence(entry)}
                    </p>
                    <p className="mt-1 text-[11px] text-muted tabular-nums">
                      {formatRelativeTime(entry.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
