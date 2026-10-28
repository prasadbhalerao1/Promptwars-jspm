"use client";

import { Label } from "@/components/ui/label";
import type { MCQAssessmentSpec } from "@/lib/api";

export function MCQForm({
  spec,
  answers,
  onChange,
}: {
  spec: MCQAssessmentSpec;
  answers: Record<string, string>;
  onChange: (answers: Record<string, string>) => void;
}) {
  return (
    <div className="space-y-6">
      {spec.questions.map((q, i) => (
        <div
          key={q.id}
          className="space-y-2"
          role={q.options && q.options.length > 0 ? "radiogroup" : undefined}
          aria-labelledby={`mcq-${q.id}-label`}
        >
          <Label
            id={`mcq-${q.id}-label`}
            htmlFor={q.options && q.options.length > 0 ? undefined : `mcq-${q.id}-input`}
          >
            {i + 1}. {q.text}
          </Label>
          {q.options && q.options.length > 0 ? (
            <div className="space-y-1">
              {q.options.map((opt) => (
                <label
                  key={opt}
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <input
                    type="radio"
                    name={q.id}
                    checked={answers[q.id] === opt}
                    onChange={() => onChange({ ...answers, [q.id]: opt })}
                  />
                  {opt}
                </label>
              ))}
            </div>
          ) : (
            <input
              id={`mcq-${q.id}-input`}
              className="w-full px-3 py-2 border rounded-md text-sm bg-background text-foreground"
              value={answers[q.id] ?? ""}
              onChange={(e) => onChange({ ...answers, [q.id]: e.target.value })}
            />
          )}
        </div>
      ))}
    </div>
  );
}
