"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Question, TableAnswer } from "@/lib/api";

const LONG_TEXT_COLUMNS = new Set([
  "use_case",
  "requirement",
  "qualification",
  "prohibited_use_case",
  "definition",
  "timeline",
]);

export function QuestionTable({
  question,
  answer,
  onChange,
}: {
  question: Question;
  answer: TableAnswer;
  onChange: (next: TableAnswer) => void;
}) {
  const updateCell = (rowIndex: number, key: string, value: string) => {
    const rows = answer.rows.map((row, i) => (i === rowIndex ? { ...row, [key]: value } : row));
    onChange({ rows });
  };

  const addRow = () => {
    const blank = Object.fromEntries(question.columns.map((c) => [c.key, ""]));
    onChange({ rows: [...answer.rows, blank] });
  };

  const removeRow = (rowIndex: number) => {
    onChange({ rows: answer.rows.filter((_, i) => i !== rowIndex) });
  };

  return (
    <div className="space-y-3">
      {answer.rows.map((row, rowIndex) => (
        <div key={rowIndex} className="rounded-lg border border-border p-3">
          {"level" in row && (
            <p className="mb-2 text-sm font-semibold text-muted-foreground">{row.level} severity</p>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {question.columns.map((col) => {
              const Field = LONG_TEXT_COLUMNS.has(col.key) ? Textarea : Input;
              return (
                <div key={col.key} className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">{col.label}</label>
                  <Field
                    value={row[col.key] ?? ""}
                    onChange={(e) => updateCell(rowIndex, col.key, e.target.value)}
                  />
                </div>
              );
            })}
          </div>
          {!question.locked_rows && (
            <div className="mt-2 flex justify-end">
              <Button type="button" variant="ghost" size="sm" onClick={() => removeRow(rowIndex)}>
                <X className="size-4" /> Remove
              </Button>
            </div>
          )}
        </div>
      ))}
      {question.addable && (
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <Plus /> Add row
        </Button>
      )}
    </div>
  );
}
