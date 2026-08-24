"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDashed, Lock, PlayCircle } from "lucide-react";

import { fetchTrainingModules, type TrainingModule } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
};

function StatusIcon({ module }: { module: TrainingModule }) {
  if (module.is_locked) return <Lock className="size-5 text-muted-foreground/50" />;
  if (module.completion_status === "completed") return <CheckCircle2 className="size-5 text-primary" />;
  if (module.completion_status === "in_progress") return <PlayCircle className="size-5 text-secondary-foreground" />;
  return <CircleDashed className="size-5 text-muted-foreground" />;
}

export default function TrainingPage() {
  const [modules, setModules] = useState<TrainingModule[]>([]);

  useEffect(() => {
    fetchTrainingModules()
      .then(setModules)
      .catch(() => setModules([]));
  }, []);

  const completedCount = modules.filter((m) => m.completion_status === "completed").length;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">Training</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Mandatory AI-usage training, in order. {modules.length > 0 && `${completedCount} of ${modules.length} completed.`}
      </p>

      <div className="mt-6 space-y-3">
        {modules.map((module) => {
          const card = (
            <div
              className={`flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-colors ${
                module.is_locked ? "opacity-50" : "hover:bg-muted"
              }`}
            >
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-sm font-semibold text-muted-foreground">
                {module.order_index}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{module.title}</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{module.description}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {module.is_locked ? "Locked" : STATUS_LABELS[module.completion_status]}
                </span>
                <StatusIcon module={module} />
              </div>
            </div>
          );
          return module.is_locked ? (
            <div key={module.id} title="Complete the previous module first">
              {card}
            </div>
          ) : (
            <Link key={module.id} href={`/training/${module.id}`}>
              {card}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
