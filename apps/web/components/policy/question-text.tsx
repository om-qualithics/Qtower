"use client";

import { Input } from "@/components/ui/input";
import type { Question, TextAnswer } from "@/lib/api";

export function QuestionText({
  question,
  answer,
  onChange,
}: {
  question: Question;
  answer: TextAnswer;
  onChange: (next: TextAnswer) => void;
}) {
  return (
    <Input
      value={answer.value}
      onChange={(e) => onChange({ value: e.target.value })}
      placeholder={question.label}
    />
  );
}
