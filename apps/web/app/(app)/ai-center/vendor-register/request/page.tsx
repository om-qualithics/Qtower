"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft, ShieldCheck, ShieldAlert, ShieldX, ShieldQuestion } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { WizardProgressBar } from "@/components/ui/wizard-progress-bar";
import { ChecklistAnswerFieldset } from "@/components/vendor/checklist-answer-fieldset";
import {
  createVendorRequest,
  fetchVendorChecklistItems,
  VendorRequestDuplicateError,
  type ChecklistAnswerValue,
  type VendorChecklistItem,
  type VendorRequestChecklistAnswer,
  type VendorType,
} from "@/lib/api";

const STEPS = [
  { id: 1, title: "Vendor type & basics" },
  { id: 2, title: "Must Have" },
  { id: 3, title: "Good to Have" },
  { id: 4, title: "Optional" },
];

const TYPE_FIELD_LABELS: Record<VendorType, { link: string; justification: string; linkPlaceholder: string }> = {
  commercial: { link: "Website", justification: "Business justification", linkPlaceholder: "https://..." },
  open_source: {
    link: "Repository / URL",
    justification: "Intended use case",
    linkPlaceholder: "https://github.com/...",
  },
};

function statusBadge(status: string) {
  const styles: Record<string, { className: string; Icon: typeof ShieldCheck }> = {
    approved: { className: "bg-primary/10 text-primary", Icon: ShieldCheck },
    needs_review: { className: "bg-accent/15 text-accent", Icon: ShieldAlert },
    restricted: { className: "bg-destructive/10 text-destructive", Icon: ShieldX },
    pending: { className: "bg-muted text-muted-foreground", Icon: ShieldQuestion },
  };
  const s = styles[status] ?? styles.pending;
  const Icon = s.Icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium capitalize ${s.className}`}>
      <Icon className="size-3.5" /> {status.replace("_", " ")}
    </span>
  );
}

export default function VendorRequestPage() {
  const router = useRouter();
  const [checklistItems, setChecklistItems] = useState<VendorChecklistItem[]>([]);

  const [currentStep, setCurrentStep] = useState(1);
  const [type, setType] = useState<VendorType>("commercial");
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [justification, setJustification] = useState("");
  const [answers, setAnswers] = useState<Record<string, ChecklistAnswerValue>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ projected_status: string | null; overall_score: number | null } | null>(null);

  useEffect(() => {
    fetchVendorChecklistItems()
      .then(setChecklistItems)
      .catch(() => setChecklistItems([]));
  }, []);

  const relevantItems = useMemo(
    () =>
      checklistItems
        .filter((item) => item.applies_to === "both" || item.applies_to === type)
        .sort((a, b) => a.sort_order - b.sort_order),
    [checklistItems, type]
  );
  const mustHaveItems = relevantItems.filter((i) => i.tier === "must_have");
  const goodToHaveItems = relevantItems.filter((i) => i.tier === "good_to_have");
  const optionalItems = relevantItems.filter((i) => i.tier === "optional");

  // Every Must Have question needs an explicit answer before moving on -
  // these are a hard gate, so silently defaulting to "not_applicable" (the
  // way Good to Have/Optional still do) would undercut the point of asking.
  const allMustHavesAnswered = mustHaveItems.every((item) => item.id in answers);

  const stepValid: Record<number, boolean> = {
    1: name.trim().length > 0 && justification.trim().length > 0,
    2: allMustHavesAnswered,
    3: true,
    4: true,
  };
  const isLastStep = currentStep === STEPS.length;

  const goBack = () => setCurrentStep((s) => Math.max(1, s - 1));

  const goNext = async () => {
    if (!stepValid[currentStep]) return;
    setError(null);
    if (!isLastStep) {
      setCurrentStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    try {
      const responses: VendorRequestChecklistAnswer[] = relevantItems.map((item) => ({
        checklist_item_id: item.id,
        answer: answers[item.id] ?? "not_applicable",
        evidence_note: notes[item.id]?.trim() || null,
      }));
      const request = await createVendorRequest(name, type, link.trim() || null, justification, responses);
      setResult({ projected_status: request.projected_status, overall_score: request.overall_score });
    } catch (err) {
      if (err instanceof VendorRequestDuplicateError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const fieldLabels = TYPE_FIELD_LABELS[type];

  if (result) {
    return (
      <div className="mx-auto max-w-xl text-center">
        <CheckCircle2 className="mx-auto mb-4 size-12 text-primary" />
        <h1 className="text-xl font-semibold">Vendor request submitted for review</h1>
        {result.projected_status && (
          <div className="mt-3 flex items-center justify-center gap-2 text-sm">
            <span className="text-muted-foreground">Projected outcome:</span>
            {statusBadge(result.projected_status)}
            {result.overall_score !== null && (
              <span className="text-xs text-muted-foreground">({Math.round(result.overall_score * 100)}%)</span>
            )}
          </div>
        )}
        <p className="mt-2 text-sm text-muted-foreground">
          A govern/assure reviewer still makes the final approve/reject call.
        </p>
        <div className="mt-6 flex justify-center">
          <Button onClick={() => router.push("/ai-center/vendor-register")}>Back to Vendor Register</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-fit max-w-full">
      <div className="w-full max-w-[clamp(32rem,28rem+17vw,56rem)]">
        <button
          type="button"
          onClick={() => router.push("/ai-center/vendor-register")}
          className="mb-2 flex items-center gap-1 text-sm text-muted-foreground transition hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> Back to Vendor Register
        </button>

        <h1 className="mb-1 text-2xl font-semibold">Request Vendor</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Ask for a commercial or open-source AI vendor to be added to the Vendor Register. Answer the compliance
          checklist so a score can be computed right away — govern/assure still makes the final approve/reject call.
        </p>

        <div className="mb-6">
          <WizardProgressBar
            steps={STEPS}
            currentStep={currentStep}
            onPrev={goBack}
            onNext={goNext}
            nextDisabled={!stepValid[currentStep] || submitting}
          />
        </div>

        <div className="rounded-2xl border border-border bg-card p-5">
          {error && (
            <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-5">
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Type</Label>
                <Select
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value as VendorType);
                    setAnswers({});
                    setNotes({});
                  }}
                >
                  <option value="commercial">Commercial</option>
                  <option value="open_source">Open source</option>
                </Select>
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude Enterprise" />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">{fieldLabels.link}</Label>
                <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder={fieldLabels.linkPlaceholder} />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">{fieldLabels.justification}</Label>
                <Textarea value={justification} onChange={(e) => setJustification(e.target.value)} rows={3} />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div>
              <p className="mb-3 text-xs text-muted-foreground">
                Every Must Have question needs an answer before continuing — any &quot;No&quot; will project this
                vendor as restricted.
              </p>
              <ChecklistAnswerFieldset
                items={mustHaveItems}
                answers={answers}
                notes={notes}
                onAnswerChange={(itemId, answer) => setAnswers((prev) => ({ ...prev, [itemId]: answer }))}
                onNoteChange={(itemId, note) => setNotes((prev) => ({ ...prev, [itemId]: note }))}
                scrollable={false}
              />
            </div>
          )}

          {currentStep === 3 && (
            <ChecklistAnswerFieldset
              items={goodToHaveItems}
              answers={answers}
              notes={notes}
              onAnswerChange={(itemId, answer) => setAnswers((prev) => ({ ...prev, [itemId]: answer }))}
              onNoteChange={(itemId, note) => setNotes((prev) => ({ ...prev, [itemId]: note }))}
              scrollable={false}
            />
          )}

          {currentStep === 4 && (
            <ChecklistAnswerFieldset
              items={optionalItems}
              answers={answers}
              notes={notes}
              onAnswerChange={(itemId, answer) => setAnswers((prev) => ({ ...prev, [itemId]: answer }))}
              onNoteChange={(itemId, note) => setNotes((prev) => ({ ...prev, [itemId]: note }))}
              scrollable={false}
            />
          )}
        </div>

        <div className="mt-5 flex justify-between">
          <Button variant="outline" onClick={goBack} disabled={currentStep === 1 || submitting}>
            <ArrowLeft /> Back
          </Button>
          <Button onClick={goNext} disabled={!stepValid[currentStep] || submitting}>
            {isLastStep ? (submitting ? "Submitting..." : "Send for Approval") : "Next"}
            {!isLastStep && <ArrowRight />}
          </Button>
        </div>
      </div>
    </div>
  );
}
