"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PolicyProgressBar } from "@/components/policy/progress-bar";
import { QuestionChecklist } from "@/components/policy/question-checklist";
import { QuestionSingleSelect } from "@/components/policy/question-single-select";
import { QuestionTable } from "@/components/policy/question-table";
import { QuestionText } from "@/components/policy/question-text";
import {
  fetchPolicySteps,
  generatePolicy,
  getPolicy,
  getPolicyDownloadUrl,
  savePolicyStep,
  PolicyGenerateValidationError,
  type AnswerValue,
  type Answers,
  type PolicyStep,
} from "@/lib/api";

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

  useEffect(() => {
    if (!policyId) return;
    Promise.all([fetchPolicySteps(), getPolicy(policyId)]).then(([fetchedSteps, policy]) => {
      setSteps(fetchedSteps);
      setAnswers(policy.answers);
      setCurrentStep(policy.status === "generated" ? fetchedSteps.length : policy.current_step);
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
    setMissingRequired([]);
    setError(null);
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
        <h1 className="text-xl font-semibold">Your AI Policy is ready</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The policy has been generated from your answers and is ready to download.
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
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-2xl font-semibold">Build your AI Policy</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Answer the questions below - your answers plug directly into the policy document.
      </p>

      <div className="mb-8">
        <PolicyProgressBar steps={steps} currentStep={currentStep} />
      </div>

      <div className="rounded-2xl border border-border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">{step.title}</h2>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {missingRequired.length > 0 && (
          <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            Please complete all required fields before generating the policy.
          </div>
        )}

        <div className="space-y-6">
          {step.questions.map((question) => {
            const answer = answers[question.key];
            return (
              <div key={question.key}>
                <label className="mb-2 block text-sm font-medium">
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
                {question.type === "table" && (
                  <QuestionTable
                    question={question}
                    answer={answer as never}
                    onChange={(next) => updateAnswer(question.key, next)}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-6 flex justify-between">
        <Button variant="outline" onClick={goBack} disabled={currentStep === 1 || saving || generating}>
          <ArrowLeft /> Back
        </Button>
        <Button onClick={goNext} disabled={saving || generating}>
          {isLastStep ? (generating ? "Generating..." : "Generate Policy") : "Next"}
          {!isLastStep && <ArrowRight />}
        </Button>
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
