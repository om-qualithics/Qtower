"use client";

import { useEffect, useRef } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Question, TableAnswer } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * A borderless textarea that grows to fit its content instead of clipping
 * or scrolling - the cell text (often a full sentence, e.g. a review
 * requirement) needs to wrap onto multiple lines rather than being cut off
 * at the column boundary the way a single-line <input> would. Because every
 * cell in a row is a sibling grid item (see the "contents" row wrapper
 * below), the tallest cell's grown height sets the whole row's height for
 * free - no manual row-height sync needed.
 */
function AutoGrowTextarea({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(
        "w-full min-w-0 resize-none overflow-hidden bg-transparent text-sm leading-snug outline-none placeholder:text-muted-foreground/60",
        className
      )}
    />
  );
}

/**
 * Compact table-style row editor - used for the two questions the user
 * asked to look like a real table (human oversight, incident severity)
 * instead of question-table.tsx's card-per-row layout, which stays as-is
 * for the other table questions (governance owner/leads/approvers, custom
 * prohibited-use categories). Header row shows column labels; each answer
 * row is a set of auto-growing borderless textareas so it reads like table
 * cells, not a form, and wraps long text instead of clipping it; a trash
 * icon ends each row unless the question locks its rows (the severity
 * table's 3 rows are fixed, per its own product design).
 */
export function QuestionCompactTable({
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

  // Some seeded rows (the severity table) carry a "level" field that isn't
  // a declared column - it's the row's own identity (High/Medium/Low), not
  // an editable cell, so it renders as a leading read-only label column
  // instead of being silently dropped.
  const hasLevel = answer.rows.some((row) => "level" in row);
  const gridCols = `${hasLevel ? "auto " : ""}repeat(${question.columns.length}, minmax(0, 1fr))${
    question.locked_rows ? "" : " auto"
  }`;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-border">
        <div className="min-w-full" style={{ display: "grid", gridTemplateColumns: gridCols }}>
          {hasLevel && (
            <div className="border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
              Severity
            </div>
          )}
          {question.columns.map((col) => (
            <div
              key={col.key}
              className="border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground"
            >
              {col.label}
            </div>
          ))}
          {!question.locked_rows && <div className="border-b border-border bg-muted/40" />}

          {answer.rows.map((row, rowIndex) => (
            <div key={rowIndex} className="contents">
              {hasLevel && (
                <div
                  className={cn(
                    "px-3 py-2 text-sm font-semibold whitespace-nowrap",
                    rowIndex < answer.rows.length - 1 && "border-b border-border/60"
                  )}
                >
                  {row.level}
                </div>
              )}
              {question.columns.map((col, colIndex) => (
                <div
                  key={col.key}
                  className={cn(
                    "flex items-start px-3 py-2",
                    rowIndex < answer.rows.length - 1 && "border-b border-border/60"
                  )}
                >
                  <AutoGrowTextarea
                    value={row[col.key] ?? ""}
                    onChange={(value) => updateCell(rowIndex, col.key, value)}
                    placeholder={col.label}
                    className={colIndex === 0 ? "font-semibold" : undefined}
                  />
                </div>
              ))}
              {!question.locked_rows && (
                <div
                  className={cn(
                    "flex items-start justify-center px-2 py-2",
                    rowIndex < answer.rows.length - 1 && "border-b border-border/60"
                  )}
                >
                  <button
                    type="button"
                    onClick={() => removeRow(rowIndex)}
                    className="rounded-md p-1 text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Remove row"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {question.addable && (
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <Plus /> Add row
        </Button>
      )}
    </div>
  );
}
