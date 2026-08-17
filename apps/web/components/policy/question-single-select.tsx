"use client";

import { cn } from "@/lib/utils";
import type { Question, SingleSelectAnswer } from "@/lib/api";

export function QuestionSingleSelect({
  question,
  answer,
  onChange,
}: {
  question: Question;
  answer: SingleSelectAnswer;
  onChange: (next: SingleSelectAnswer) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {question.options.map((option) => {
        const active = answer.selected === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange({ selected: option.value })}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-background hover:bg-muted"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
