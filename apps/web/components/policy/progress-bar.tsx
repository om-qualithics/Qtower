import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * "Minimal with step count" style - a prev/current/next step-title strip
 * above a thin progress bar with "Step N of M" alongside it, replacing the
 * old full step-title-list + wide bar layout. The prev/next pills are real
 * navigation (not just a label) - clicking them calls the same
 * onPrev/onNext handlers as the wizard's Back/Next buttons, so validation
 * gating on "next" applies identically either way.
 */
export function PolicyProgressBar({
  steps,
  currentStep,
  onPrev,
  onNext,
  nextDisabled,
}: {
  steps: { id: number; title: string }[];
  currentStep: number;
  onPrev: () => void;
  onNext: () => void;
  nextDisabled: boolean;
}) {
  const current = steps.find((s) => s.id === currentStep);
  const prev = steps.find((s) => s.id === currentStep - 1);
  const next = steps.find((s) => s.id === currentStep + 1);
  const percent = (currentStep / steps.length) * 100;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        {prev ? (
          <button
            type="button"
            onClick={onPrev}
            className="flex shrink-0 items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <ChevronLeft className="size-3.5" />
            {prev.title}
          </button>
        ) : (
          <span />
        )}

        <span className="truncate text-center text-sm font-semibold">{current?.title}</span>

        {next ? (
          <button
            type="button"
            onClick={onNext}
            disabled={nextDisabled}
            className={cn(
              "flex shrink-0 items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium transition",
              nextDisabled
                ? "cursor-not-allowed text-muted-foreground/50"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {next.title}
            <ChevronRight className="size-3.5" />
          </button>
        ) : (
          <span />
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          Step {currentStep} of {steps.length}
        </span>
      </div>
    </div>
  );
}
