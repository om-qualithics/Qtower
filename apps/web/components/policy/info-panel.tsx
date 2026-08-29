"use client";

import { ChevronRight, ChevronLeft } from "lucide-react";

import { POLICY_INFO_PANEL } from "@/lib/policy-info-panel";
import { cn } from "@/lib/utils";

/**
 * AWS-console-style contextual help rail - a collapsible panel to the
 * right of the wizard, swapping content to match whichever step is
 * currently on screen. Collapsed state is local (not persisted) - it's a
 * per-visit reading-space toggle, not a saved preference.
 */
export function PolicyInfoPanel({
  stepId,
  collapsed,
  onToggleCollapsed,
}: {
  stepId: number;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const entry = POLICY_INFO_PANEL[stepId];

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label="Show section guidance"
        className="sticky top-6 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition hover:bg-muted hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
      </button>
    );
  }

  return (
    <aside className="sticky top-6 w-[clamp(16rem,20vw,22rem)] shrink-0 overflow-hidden rounded-2xl border border-border bg-card">
      <button
        type="button"
        onClick={onToggleCollapsed}
        className="flex w-full items-center justify-between border-b border-border px-4 py-3 text-left transition hover:bg-muted"
      >
        <span className="text-sm font-semibold">{entry?.title ?? "Guidance"}</span>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </button>

      {entry && (
        <div className="max-h-[calc(100vh-10rem)] space-y-4 overflow-y-auto p-4 text-sm">
          <div>
            <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              What is this section
            </p>
            <p className="text-foreground/90">{entry.whatIsThis}</p>
          </div>

          <div>
            <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Why it matters
            </p>
            <p className="text-foreground/90">{entry.whyItMatters}</p>
          </div>

          <div>
            <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Adaptation</p>
            <ul className="space-y-1.5">
              {entry.adaptation.map((item, i) => (
                <li key={i} className={cn("flex gap-2 text-foreground/90", "before:mt-2 before:size-1 before:shrink-0 before:rounded-full before:bg-muted-foreground before:content-['']")}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </aside>
  );
}
