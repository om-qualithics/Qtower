"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { ChecklistAnswer, Question } from "@/lib/api";

export function QuestionChecklist({
  question,
  answer,
  onChange,
}: {
  question: Question;
  answer: ChecklistAnswer;
  onChange: (next: ChecklistAnswer) => void;
}) {
  const toggle = (value: string, checked: boolean) => {
    const selected = checked ? [...answer.selected, value] : answer.selected.filter((v) => v !== value);
    onChange({ ...answer, selected });
  };

  const updateOther = (index: number, value: string) => {
    const other = [...answer.other];
    other[index] = value;
    onChange({ ...answer, other });
  };

  const addOther = () => onChange({ ...answer, other: [...answer.other, ""] });
  const removeOther = (index: number) => onChange({ ...answer, other: answer.other.filter((_, i) => i !== index) });

  return (
    <div className="space-y-1.5">
      {question.options.map((option) => (
        <label
          key={option.value}
          className="flex items-start gap-2.5 rounded-lg p-1.5 text-sm hover:bg-muted"
        >
          <Checkbox
            checked={answer.selected.includes(option.value)}
            onCheckedChange={(checked) => toggle(option.value, checked === true)}
            className="mt-0.5"
          />
          <span>{option.label}</span>
        </label>
      ))}
      {question.allow_other && (
        <div className="space-y-2 pt-1">
          {answer.other.map((item, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input value={item} onChange={(e) => updateOther(index, e.target.value)} placeholder="Add your own..." />
              <Button type="button" variant="ghost" size="icon-sm" onClick={() => removeOther(index)}>
                <X className="size-4" />
              </Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addOther}>
            <Plus /> Add custom item
          </Button>
        </div>
      )}
    </div>
  );
}
