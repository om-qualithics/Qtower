"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { WizardProgressBar } from "@/components/ui/wizard-progress-bar";
import { TIER_KEYS, TIER_LABELS } from "@/lib/tiers";
import { createToolRequest, ToolRequestDuplicateError, type ToolRequestType } from "@/lib/api";

const MIN_USE_CASE_WORDS = 150;

const STEPS = [
  { id: 1, title: "Basics" },
  { id: 2, title: "Use case" },
  { id: 3, title: "Classification" },
];

function wordCount(text: string): number {
  return text.trim().length === 0 ? 0 : text.trim().split(/\s+/).length;
}

export default function ToolRequestPage() {
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState(1);
  const [requestType, setRequestType] = useState<ToolRequestType>("tool");
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [useCase, setUseCase] = useState("");
  const [dataTiers, setDataTiers] = useState<string[]>([]);
  const [requiresEnterpriseAccount, setRequiresEnterpriseAccount] = useState<"" | "yes" | "no">("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const useCaseWords = wordCount(useCase);

  const stepValid: Record<number, boolean> = {
    1: name.trim().length > 0 && link.trim().length > 0,
    2: useCaseWords >= MIN_USE_CASE_WORDS,
    3: dataTiers.length > 0 && requiresEnterpriseAccount !== "",
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
      await createToolRequest(requestType, name, link, useCase, dataTiers, requiresEnterpriseAccount === "yes");
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ToolRequestDuplicateError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="mx-auto max-w-xl text-center">
        <CheckCircle2 className="mx-auto mb-4 size-12 text-primary" />
        <h1 className="text-xl font-semibold">Request submitted for review</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          An AI precheck runs automatically if your org has an active policy - a govern/assure reviewer will make
          the final call.
        </p>
        <div className="mt-6 flex justify-center">
          <Button onClick={() => router.push("/ai-center/tools")}>Back to AI Tools</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-fit max-w-full">
      <div className="w-full max-w-[clamp(32rem,28rem+17vw,56rem)]">
        <button
          type="button"
          onClick={() => router.push("/ai-center/tools")}
          className="mb-2 flex items-center gap-1 text-sm text-muted-foreground transition hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> Back to AI Tools
        </button>

        <h1 className="mb-1 text-2xl font-semibold">Request Access</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Ask for approval to use an AI tool, feature, or web extension not already on the approved list.
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
                <Label className="mb-1.5 block text-sm font-medium">Approval request for?</Label>
                <Select value={requestType} onChange={(e) => setRequestType(e.target.value as ToolRequestType)}>
                  <option value="tool">Tool</option>
                  <option value="feature">Feature</option>
                  <option value="webextension">Web extension</option>
                </Select>
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude" />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Link</Label>
                <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://..." />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div>
              <Label className="mb-1.5 block text-sm font-medium">Intended use case</Label>
              <Textarea value={useCase} onChange={(e) => setUseCase(e.target.value)} rows={8} />
              <p className={`mt-1.5 text-xs ${useCaseWords >= MIN_USE_CASE_WORDS ? "text-primary" : "text-muted-foreground"}`}>
                {useCaseWords} / {MIN_USE_CASE_WORDS} words minimum
              </p>
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-5">
              <div>
                <Label className="mb-1.5 block text-sm font-medium">What class of data tier will be used?</Label>
                <div className="space-y-2">
                  {TIER_KEYS.map((tier) => (
                    <label key={tier} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={dataTiers.includes(tier)}
                        onCheckedChange={(checked) =>
                          setDataTiers((prev) => (checked ? [...prev, tier] : prev.filter((t) => t !== tier)))
                        }
                      />
                      {TIER_LABELS[tier]}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Does this require an enterprise account?</Label>
                <Select
                  value={requiresEnterpriseAccount}
                  onChange={(e) => setRequiresEnterpriseAccount(e.target.value as "" | "yes" | "no")}
                >
                  <option value="" disabled>
                    Select one
                  </option>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </Select>
              </div>
            </div>
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
