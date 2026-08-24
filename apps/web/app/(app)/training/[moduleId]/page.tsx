"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  completeTrainingModule,
  fetchTrainingModule,
  saveTrainingProgress,
  TrainingLockedError,
  type TrainingModule,
} from "@/lib/api";

function VideoArea({ module }: { module: TrainingModule }) {
  if (module.video_type === "file" && module.video_url) {
    return (
      <video controls className="aspect-video w-full rounded-xl bg-black">
        <source src={module.video_url} />
      </video>
    );
  }
  if (module.video_type === "embed" && module.video_url) {
    return (
      <iframe
        src={module.video_url}
        className="aspect-video w-full rounded-xl border border-border"
        allow="autoplay; fullscreen"
      />
    );
  }
  return (
    <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-border bg-muted">
      <p className="text-sm text-muted-foreground">Video coming soon</p>
    </div>
  );
}

export default function TrainingModulePage() {
  const params = useParams<{ moduleId: string }>();
  const router = useRouter();
  const [module, setModule] = useState<TrainingModule | "loading" | null>("loading");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrainingModule(params.moduleId)
      .then((m) => {
        setModule(m);
        setAnswers(m.answers);
      })
      .catch((err) => {
        if (err instanceof TrainingLockedError) {
          router.replace("/training");
          return;
        }
        setModule(null);
      });
  }, [params.moduleId, router]);

  if (module === "loading") {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }
  if (module === null) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-muted-foreground">Module not found.</p>
        <Link href="/training" className="mt-2 inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="size-4" /> Back to Training
        </Link>
      </div>
    );
  }

  const allAnswered = module.questions.every((q) => (answers[q.id] ?? "").trim().length > 0);

  const persistAnswer = (questionId: string, value: string) => {
    saveTrainingProgress(module.id, { [questionId]: value }).catch(() => {
      // Best-effort autosave - the user can still complete the module,
      // which re-validates and surfaces any real problem then.
    });
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/training" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to Training
      </Link>

      <h1 className="text-2xl font-semibold">
        {module.order_index}. {module.title}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">{module.description}</p>

      <div className="mt-6">
        <VideoArea module={module} />
      </div>

      <p className="mt-6 whitespace-pre-line text-sm leading-relaxed">{module.body_text}</p>

      {module.questions.length > 0 && (
        <div className="mt-8 space-y-5">
          <h2 className="text-sm font-semibold text-muted-foreground">Checkpoint questions</h2>
          {module.questions.map((q, i) => (
            <div key={q.id} className="rounded-2xl border border-border bg-card p-4">
              <Label className="mb-2 block text-sm">
                {i + 1}. {q.prompt}
              </Label>
              {q.options ? (
                <Select
                  value={answers[q.id] ?? ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    setAnswers((prev) => ({ ...prev, [q.id]: value }));
                    if (value) persistAnswer(q.id, value);
                  }}
                >
                  <option value="" disabled>
                    Select an answer
                  </option>
                  {q.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </Select>
              ) : (
                <Textarea
                  rows={2}
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  onBlur={(e) => e.target.value.trim() && persistAnswer(q.id, e.target.value)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mt-8 flex justify-end">
        {module.completion_status === "completed" ? (
          <span className="flex items-center gap-2 text-sm font-medium text-primary">
            <CheckCircle2 className="size-4" /> Completed
          </span>
        ) : (
          <Button
            disabled={completing || !allAnswered}
            onClick={async () => {
              setCompleting(true);
              setError(null);
              try {
                for (const [id, value] of Object.entries(answers)) {
                  await saveTrainingProgress(module.id, { [id]: value });
                }
                await completeTrainingModule(module.id);
                router.replace("/training");
              } catch (err) {
                setError(err instanceof Error ? err.message : "Something went wrong.");
              } finally {
                setCompleting(false);
              }
            }}
          >
            Mark Complete
          </Button>
        )}
      </div>
    </div>
  );
}
