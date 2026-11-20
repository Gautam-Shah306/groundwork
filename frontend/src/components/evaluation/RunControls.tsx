import { useState } from "react";
import { Play } from "lucide-react";
import { Button, Card } from "../ui";
import type { CreateEvalRunPayload } from "../../lib/api";

export interface RunControlsProps {
  onStartRun: (payload: CreateEvalRunPayload) => Promise<void>;
  isRunning: boolean;
  configuredModel?: string;
  disabled?: boolean;
}

export function RunControls({
  onStartRun,
  isRunning,
  configuredModel = "openai/gpt-oss-20b",
  disabled = false,
}: RunControlsProps) {
  const [sampleSize, setSampleSize] = useState<number>(150);
  const [checkDrafts, setCheckDrafts] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isRunning || disabled || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onStartRun({
        sample_size: sampleSize,
        drafts_sample: checkDrafts ? 21 : 0,
        model: configuredModel,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          {/* Sample size selector */}
          <div className="space-y-2">
            <label className="text-[12px] font-semibold uppercase tracking-wider text-muted">
              Sample Size
            </label>
            <div
              role="radiogroup"
              aria-label="Sample Size"
              className="inline-flex rounded-button border border-border bg-surface-subtle p-1"
            >
              {[
                { value: 20, label: "20 (Smoke)" },
                { value: 50, label: "50" },
                { value: 150, label: "150 (Full Test Set)" },
              ].map((opt) => {
                const isSelected = sampleSize === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => setSampleSize(opt.value)}
                    disabled={isRunning || disabled}
                    className={[
                      "rounded-button px-3 py-1.5 text-[13px] font-medium transition-colors",
                      isSelected
                        ? "bg-surface text-ink shadow-sm"
                        : "text-muted hover:text-ink",
                      isRunning || disabled ? "cursor-not-allowed opacity-60" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model info */}
          <div className="space-y-2">
            <label className="text-[12px] font-semibold uppercase tracking-wider text-muted">
              Model
            </label>
            <div className="rounded-button border border-border bg-surface px-3 py-1.5 text-[13px] text-ink">
              <span className="font-mono">{configuredModel}</span>
            </div>
          </div>

          {/* Draft flag check toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="eval-check-drafts"
              checked={checkDrafts}
              onChange={(e) => setCheckDrafts(e.target.checked)}
              disabled={isRunning || disabled}
              className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
            />
            <label
              htmlFor="eval-check-drafts"
              className="text-[13px] text-ink cursor-pointer select-none"
            >
              Also check draft replies on first 21 tickets
            </label>
          </div>

          {/* Submit button */}
          <div>
            <Button
              type="submit"
              variant="primary"
              disabled={isRunning || disabled || isSubmitting}
              className="w-full sm:w-auto"
            >
              <Play size={14} className="mr-1.5 fill-current" />
              {isSubmitting ? "Starting..." : isRunning ? "Evaluation Running" : "Run evaluation"}
            </Button>
          </div>
        </div>

        <p className="text-[12px] text-muted">
          Runs in background with 2 s pacing. Estimated time: ~20s for 20, ~2m for 50, ~5m for 150.
        </p>
      </form>
    </Card>
  );
}
