import { useRef, useState, type FormEvent } from "react";
import { AlertCircle, Briefcase, CheckCircle2, Plus, Trash2 } from "lucide-react";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  Eyebrow,
  StatusPill,
  SyntheticDataNotice,
  type DataTableColumn,
} from "../components/ui";
import { useEngagement } from "../context/EngagementContext";
import type { Engagement, EngagementStage } from "../lib/api";
import {
  ENGAGEMENT_STAGES,
  STAGE_LABELS,
  STAGE_PILL_VARIANTS,
  formatShortDate,
} from "../lib/format";

interface FormErrors {
  name?: string;
  client_name?: string;
  client_statement?: string;
  form?: string;
}

export function EngagementsPage() {
  const {
    engagements,
    loading,
    error,
    activeEngagementId,
    selectEngagement,
    refreshEngagements,
    createEngagement,
    deleteEngagement,
  } = useEngagement();

  const nameInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [industry, setIndustry] = useState("");
  const [stage, setStage] = useState<EngagementStage>("discover");
  const [clientStatement, setClientStatement] = useState("");
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const validateForm = (): FormErrors => {
    const nextErrors: FormErrors = {};
    const trimmedName = name.trim();
    const trimmedClient = clientName.trim();
    const trimmedStatement = clientStatement.trim();

    if (!trimmedName) {
      nextErrors.name = "Engagement name is required.";
    } else if (trimmedName.length > 120) {
      nextErrors.name = "Engagement name must be 120 characters or fewer.";
    }

    if (!trimmedClient) {
      nextErrors.client_name = "Client name is required.";
    } else if (trimmedClient.length > 120) {
      nextErrors.client_name = "Client name must be 120 characters or fewer.";
    }

    if (trimmedStatement.length > 2000) {
      nextErrors.client_statement =
        "Client statement must be 2000 characters or fewer.";
    }

    return nextErrors;
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage(null);
    setActionError(null);

    const validation = validateForm();
    if (Object.keys(validation).length > 0) {
      setFormErrors(validation);
      return;
    }

    setFormErrors({});
    setSubmitting(true);
    try {
      const created = await createEngagement({
        name: name.trim(),
        client_name: clientName.trim(),
        industry: industry.trim(),
        stage,
        client_statement: clientStatement.trim(),
        is_synthetic: true,
      });
      setName("");
      setClientName("");
      setIndustry("");
      setStage("discover");
      setClientStatement("");
      setStatusMessage(`Created engagement "${created.name}".`);
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Unable to create engagement. Please try again.";
      setFormErrors({ form: message });
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDelete = async (engagement: Engagement) => {
    setStatusMessage(null);
    setActionError(null);
    setDeletingId(engagement.id);
    try {
      await deleteEngagement(engagement.id);
      setConfirmDeleteId(null);
      setStatusMessage(`Deleted engagement "${engagement.name}".`);
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Unable to delete engagement.";
      setActionError(message);
    } finally {
      setDeletingId(null);
    }
  };

  const columns: DataTableColumn<Engagement & Record<string, unknown>>[] = [
    {
      key: "name",
      header: "Engagement",
      render: (row) => (
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-ink">{row.name}</span>
            {row.id === activeEngagementId && (
              <StatusPill variant="info" label="Active" />
            )}
          </div>
          {row.industry && (
            <div className="text-[11px] text-muted">{row.industry}</div>
          )}
        </div>
      ),
    },
    {
      key: "client_name",
      header: "Client",
    },
    {
      key: "stage",
      header: "Stage",
      render: (row) => (
        <StatusPill
          variant={STAGE_PILL_VARIANTS[row.stage]}
          label={STAGE_LABELS[row.stage]}
        />
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (row) => (
        <span className="tabular-nums text-muted">
          {formatShortDate(row.created_at)}
        </span>
      ),
    },
    {
      key: "is_synthetic",
      header: "Data source",
      render: (row) => (
        <StatusPill
          variant={row.is_synthetic ? "warning" : "neutral"}
          label={row.is_synthetic ? "Synthetic data" : "Client supplied"}
        />
      ),
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (row) => {
        const isActive = row.id === activeEngagementId;
        const isConfirming = confirmDeleteId === row.id;
        const isDeleting = deletingId === row.id;

        return (
          <div className="flex flex-wrap items-center justify-end gap-2">
            {!isConfirming && (
              <Button
                variant="secondary"
                disabled={isActive}
                onClick={() => selectEngagement(row.id)}
              >
                {isActive ? "Selected" : "Set active"}
              </Button>
            )}

            {isConfirming ? (
              <>
                <Button
                  variant="destructive"
                  loading={isDeleting}
                  onClick={() => void handleConfirmDelete(row)}
                >
                  Confirm delete
                </Button>
                <Button
                  variant="secondary"
                  disabled={isDeleting}
                  onClick={() => setConfirmDeleteId(null)}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button
                variant="tertiary"
                icon={<Trash2 size={15} strokeWidth={1.75} />}
                aria-label={`Delete ${row.name}`}
                onClick={() => setConfirmDeleteId(row.id)}
              >
                Delete
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  const tableRows = engagements as Array<Engagement & Record<string, unknown>>;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <Eyebrow>Workspace</Eyebrow>
          <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
            Engagements
          </h1>
        </div>
        <Button
          variant="primary"
          icon={<Plus size={16} strokeWidth={1.75} />}
          onClick={() => nameInputRef.current?.focus()}
        >
          New engagement
        </Button>
      </header>

      {engagements.some((item) => item.is_synthetic) && <SyntheticDataNotice />}

      {statusMessage && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-card border border-success/25 bg-success-soft px-4 py-3 text-[13px] font-medium text-success"
        >
          <CheckCircle2 size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{statusMessage}</span>
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger-soft px-4 py-3 text-[13px] font-medium text-danger"
        >
          <AlertCircle size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{actionError}</span>
        </div>
      )}

      {!loading && !error && engagements.length === 0 ? (
        <EmptyState
          eyebrow="Synthetic workspace"
          title="No engagements created yet"
          description="Client engagements and their synthetic demonstration datasets will be listed here once created below or seeded via the backend CLI."
          icon={<Briefcase size={16} strokeWidth={1.75} aria-hidden="true" />}
        />
      ) : (
        <DataTable
          caption="Operational engagements"
          columns={columns}
          data={tableRows}
          rowKey={(row) => String(row.id)}
          loading={loading}
          error={error}
          onRetry={() => void refreshEngagements()}
        />
      )}

      <Card
        title="Create engagement"
        description="Start a new synthetic operational workspace. Required fields are marked with an asterisk."
      >
        <form onSubmit={handleCreate} noValidate className="space-y-4">
          {formErrors.form && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-control border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-[12px] text-danger"
            >
              <AlertCircle
                size={15}
                strokeWidth={1.75}
                aria-hidden="true"
                className="mt-0.5 shrink-0"
              />
              <span>{formErrors.form}</span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <label
                htmlFor="engagement-name"
                className="block text-[12px] font-semibold text-ink"
              >
                Engagement name <span className="text-danger">*</span>
              </label>
              <input
                ref={nameInputRef}
                id="engagement-name"
                name="name"
                type="text"
                required
                aria-required="true"
                aria-invalid={Boolean(formErrors.name)}
                aria-describedby={
                  formErrors.name ? "engagement-name-error" : undefined
                }
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g., Kora Living: Order support triage"
                className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-muted/70 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent"
              />
              {formErrors.name && (
                <p
                  id="engagement-name-error"
                  role="alert"
                  className="text-[12px] font-medium text-danger"
                >
                  {formErrors.name}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="engagement-client"
                className="block text-[12px] font-semibold text-ink"
              >
                Client name <span className="text-danger">*</span>
              </label>
              <input
                id="engagement-client"
                name="client_name"
                type="text"
                required
                aria-required="true"
                aria-invalid={Boolean(formErrors.client_name)}
                aria-describedby={
                  formErrors.client_name ? "engagement-client-error" : undefined
                }
                value={clientName}
                onChange={(event) => setClientName(event.target.value)}
                placeholder="e.g., Kora Living"
                className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-muted/70 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent"
              />
              {formErrors.client_name && (
                <p
                  id="engagement-client-error"
                  role="alert"
                  className="text-[12px] font-medium text-danger"
                >
                  {formErrors.client_name}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="engagement-industry"
                className="block text-[12px] font-semibold text-ink"
              >
                Industry <span className="font-normal text-muted">(optional)</span>
              </label>
              <input
                id="engagement-industry"
                name="industry"
                type="text"
                value={industry}
                onChange={(event) => setIndustry(event.target.value)}
                placeholder="e.g., D2C home-goods retail"
                className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-muted/70 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="engagement-stage"
                className="block text-[12px] font-semibold text-ink"
              >
                Starting stage
              </label>
              <select
                id="engagement-stage"
                name="stage"
                value={stage}
                onChange={(event) =>
                  setStage(event.target.value as EngagementStage)
                }
                className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent"
              >
                {ENGAGEMENT_STAGES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="engagement-statement"
              className="block text-[12px] font-semibold text-ink"
            >
              Initial client statement{" "}
              <span className="font-normal text-muted">(optional, max 2000 chars)</span>
            </label>
            <textarea
              id="engagement-statement"
              name="client_statement"
              rows={3}
              aria-invalid={Boolean(formErrors.client_statement)}
              aria-describedby={
                formErrors.client_statement
                  ? "engagement-statement-error"
                  : undefined
              }
              value={clientStatement}
              onChange={(event) => setClientStatement(event.target.value)}
              placeholder="Capture the stakeholder's initial description verbatim before investigation."
              className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-muted/70 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent"
            />
            {formErrors.client_statement && (
              <p
                id="engagement-statement-error"
                role="alert"
                className="text-[12px] font-medium text-danger"
              >
                {formErrors.client_statement}
              </p>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-1">
            <Button type="submit" variant="primary" loading={submitting}>
              Create engagement
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
