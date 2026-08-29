"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PolicyInfoPanel } from "@/components/policy/info-panel";
import { PolicyProgressBar } from "@/components/policy/progress-bar";
import { QuestionChecklist } from "@/components/policy/question-checklist";
import { QuestionCompactTable } from "@/components/policy/question-compact-table";
import { QuestionSingleSelect } from "@/components/policy/question-single-select";
import { QuestionTable } from "@/components/policy/question-table";
import { QuestionText } from "@/components/policy/question-text";
import {
  fetchPolicySteps,
  generatePolicy,
  getPolicy,
  getPolicyDownloadUrl,
  isQuestionAnswered,
  savePolicyStep,
  PolicyGenerateValidationError,
  type AnswerValue,
  type Answers,
  type PolicyStep,
} from "@/lib/api";

// The two table questions the user wants rendered as a real compact table
// (header row + trash icon) instead of question-table.tsx's card-per-row
// layout, which stays the default for every other table question.
const COMPACT_TABLE_KEYS = new Set(["q5_1_human_oversight", "q6_2_severity"]);

function PolicyWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const policyId = searchParams.get("id");

  const [steps, setSteps] = useState<PolicyStep[] | null>(null);
  const [answers, setAnswers] = useState<Answers | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [missingRequired, setMissingRequired] = useState<string[]>([]);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  useEffect(() => {
    if (!policyId) return;
    Promise.all([fetchPolicySteps(), getPolicy(policyId)]).then(([fetchedSteps, policy]) => {
      setSteps(fetchedSteps);
      setAnswers(policy.answers);
      setCurrentStep(policy.generated_at ? fetchedSteps.length : policy.current_step);
    });
  }, [policyId]);

  if (!policyId) {
    return <p className="text-sm text-muted-foreground">Missing policy id.</p>;
  }
  if (!steps || !answers) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  const step = steps.find((s) => s.id === currentStep) ?? steps[0];
  const isLastStep = currentStep === steps.length;

  // Required questions on the CURRENT step that aren't answered yet - the
  // user asked that this block moving forward, not just be caught at final
  // "Generate Policy" time like before.
  const stepMissing = step.questions.filter((q) => q.required && !isQuestionAnswered(q, answers[q.key]));

  const updateAnswer = (key: string, value: AnswerValue) => {
    setAnswers((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  // `resumeStep` is persisted as Policy.current_step - where a reload should
  // land the user - which is NOT the same as "which step's questions are
  // being saved" (always the step currently on screen). Conflating the two
  // meant finishing step 2 and reloading dropped the user back on step 2
  // instead of resuming on step 3.
  const saveCurrentStep = async (resumeStep: number) => {
    const stepAnswers: Answers = {};
    for (const q of step.questions) {
      stepAnswers[q.key] = answers[q.key];
    }
    setSaving(true);
    try {
      await savePolicyStep(policyId, resumeStep, stepAnswers);
    } finally {
      setSaving(false);
    }
  };

  const goNext = async () => {
    setError(null);
    if (stepMissing.length > 0) {
      setMissingRequired(stepMissing.map((q) => q.category ?? q.label));
      return;
    }
    setMissingRequired([]);
    try {
      if (isLastStep) {
        await saveCurrentStep(currentStep);
        setGenerating(true);
        try {
          await generatePolicy(policyId);
          const url = await getPolicyDownloadUrl(policyId);
          setDownloadUrl(url);
        } catch (err) {
          if (err instanceof PolicyGenerateValidationError) {
            setMissingRequired(err.missingRequired);
          } else {
            throw err;
          }
        } finally {
          setGenerating(false);
        }
      } else {
        await saveCurrentStep(currentStep + 1);
        setCurrentStep((s) => s + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  };

  const goBack = async () => {
    setError(null);
    setMissingRequired([]);
    try {
      const resumeStep = Math.max(1, currentStep - 1);
      await saveCurrentStep(resumeStep);
      setCurrentStep(resumeStep);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  };

  if (downloadUrl) {
    return (
      <div className="mx-auto max-w-xl text-center">
        <CheckCircle2 className="mx-auto mb-4 size-12 text-primary" />
        <h1 className="text-xl font-semibold">Your draft is ready for review</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The document has been generated from your answers. Download it to review, then approve it
          from the AI Policy page to make it the live policy.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Button render={<a href={downloadUrl}>Download policy</a>} nativeButton={false} />
          <Button variant="outline" onClick={() => router.push("/policy")}>
            Back to AI Policy
          </Button>
        </div>
      </div>
    );
  }

  return (
    // w-fit (not w-full) is deliberate: this content block - header +
    // the card/panel row below - should size to its own content and then
    // center as one unit via mx-auto, matching every other page in this
    // app (/policy, /tools, /dashboard all use `mx-auto max-w-*`). w-full
    // was the bug the user caught - it stretched this container to fill
    // the whole main area regardless of content width, so flex-1 on the
    // left column then grew to fill that leftover space while the card
    // inside stayed capped by its own clamp(), leaving a dead gap between
    // the card and the panel. With w-fit, the outer box's width comes
    // from its widest child (the row), so the header above lines up with
    // the row's left edge instead of independently spanning full-width.
    <div className="mx-auto w-fit max-w-full">
      <div className="w-full max-w-[clamp(32rem,28rem+17vw,56rem)]">
        <button
          type="button"
          onClick={() => router.push("/policy")}
          className="mb-2 flex items-center gap-1 text-sm text-muted-foreground transition hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> Back to AI Policy
        </button>

        <h1 className="mb-1 text-2xl font-semibold">Build your AI Policy</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Answer the questions below - your answers plug directly into the policy document.
        </p>

        <div className="mb-6">
          <PolicyProgressBar
            steps={steps}
            currentStep={currentStep}
            onPrev={goBack}
            onNext={goNext}
            nextDisabled={stepMissing.length > 0 || saving || generating}
          />
        </div>
      </div>

      <div className="flex items-start gap-6">
        <div className="min-w-0">
          <div className="w-full max-w-[clamp(32rem,28rem+17vw,56rem)]">
            <div className="rounded-2xl border border-border bg-card p-5">
              <h2 className="mb-3 text-lg font-semibold">{step.title}</h2>

              {error && (
                <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              {missingRequired.length > 0 && (
                <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  Please complete the following required field{missingRequired.length > 1 ? "s" : ""} before
                  continuing: {missingRequired.join(", ")}
                </div>
              )}

              <div className="space-y-5">
                {step.questions.map((question) => {
                  const answer = answers[question.key];
                  return (
                    <div key={question.key}>
                      <label className="mb-1.5 block text-sm font-medium">
                        {question.category ?? question.label}
                        {question.required && <span className="ml-1 text-destructive">*</span>}
                      </label>
                      {question.type === "checklist" && (
                        <QuestionChecklist
                          question={question}
                          answer={answer as never}
                          onChange={(next) => updateAnswer(question.key, next)}
                        />
                      )}
                      {question.type === "single_select" && (
                        <QuestionSingleSelect
                          question={question}
                          answer={answer as never}
                          onChange={(next) => updateAnswer(question.key, next)}
                        />
                      )}
                      {question.type === "text" && (
                        <QuestionText
                          question={question}
                          answer={answer as never}
                          onChange={(next) => updateAnswer(question.key, next)}
                        />
                      )}
                      {question.type === "table" &&
                        (COMPACT_TABLE_KEYS.has(question.key) ? (
                          <QuestionCompactTable
                            question={question}
                            answer={answer as never}
                            onChange={(next) => updateAnswer(question.key, next)}
                          />
                        ) : (
                          <QuestionTable
                            question={question}
                            answer={answer as never}
                            onChange={(next) => updateAnswer(question.key, next)}
                          />
                        ))}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-5 flex justify-between">
              <Button variant="outline" onClick={goBack} disabled={currentStep === 1 || saving || generating}>
                <ArrowLeft /> Back
              </Button>
              <Button onClick={goNext} disabled={saving || generating || stepMissing.length > 0}>
                {isLastStep ? (generating ? "Generating..." : "Generate Policy") : "Next"}
                {!isLastStep && <ArrowRight />}
              </Button>
            </div>
          </div>
        </div>

        <PolicyInfoPanel
          stepId={currentStep}
          collapsed={panelCollapsed}
          onToggleCollapsed={() => setPanelCollapsed((c) => !c)}
        />
      </div>
    </div>
  );
}

export default function PolicyNewPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading...</p>}>
      <PolicyWizard />
    </Suspense>
  );
}
