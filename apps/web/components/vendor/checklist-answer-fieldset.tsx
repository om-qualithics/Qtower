"use client";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { type ChecklistAnswerValue, type VendorChecklistItem } from "@/lib/api";

export const CHECKLIST_TIER_LABELS: Record<string, string> = {
  must_have: "Must Have",
  good_to_have: "Good to Have",
  optional: "Optional",
};

// Shared by the Vendor Register catalog's post-approval "Edit Checklist"
// form (vendor-register/page.tsx) and the new commercial/open-source
// request wizards (Milestone 18) - same shape (Select + optional evidence
// note per item, grouped by tier), only the caller differs in what it
// does with the resulting answers/notes maps. Passing it a tier-prefiltered
// subset of items also works unchanged - each wizard step does exactly
// that to render one tier per step.
export function ChecklistAnswerFieldset({
  items,
  answers,
  notes,
  onAnswerChange,
  onNoteChange,
  scrollable = true,
}: {
  items: VendorChecklistItem[];
  answers: Record<string, ChecklistAnswerValue>;
  notes: Record<string, string>;
  onAnswerChange: (itemId: string, answer: ChecklistAnswerValue) => void;
  onNoteChange: (itemId: string, note: string) => void;
  // Dialog-hosted callers (a bounded-height popup) want the internal
  // scrollbox; a full wizard step (already scrollable as a page, one tier
  // per step) doesn't - defaults to true to match every existing caller.
  scrollable?: boolean;
}) {
  const tiers: Array<"must_have" | "good_to_have" | "optional"> = ["must_have", "good_to_have", "optional"];
  return (
    <div className={scrollable ? "max-h-96 space-y-4 overflow-y-auto" : "space-y-4"}>
      {tiers.map((tier) => {
        const tierItems = items.filter((i) => i.tier === tier);
        if (tierItems.length === 0) return null;
        return (
          <div key={tier}>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">{CHECKLIST_TIER_LABELS[tier]}</p>
            <div className="space-y-2">
              {tierItems.map((item) => (
                <div key={item.id} className="rounded-lg border border-border p-2.5">
                  <p className="mb-1.5 text-sm">{item.question}</p>
                  <div className="flex gap-2">
                    <Select
                      className="w-32"
                      value={answers[item.id] ?? "not_applicable"}
                      onChange={(e) => onAnswerChange(item.id, e.target.value as ChecklistAnswerValue)}
                    >
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                      <option value="partial">Partial</option>
                      <option value="not_applicable">N/A</option>
                    </Select>
                    <Input
                      className="flex-1"
                      placeholder="Evidence note (optional)"
                      value={notes[item.id] ?? ""}
                      onChange={(e) => onNoteChange(item.id, e.target.value)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
