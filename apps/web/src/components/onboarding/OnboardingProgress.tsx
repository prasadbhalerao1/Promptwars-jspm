"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export interface WizardStep {
  id: string;
  title: string;
  blurb: string;
}

/** Step rail for the onboarding wizard.
 *
 * Rendered at a fixed height whatever the step, so advancing never shifts the form
 * below it. Completed steps stay visible rather than collapsing — seeing what's done
 * and what's left is most of what makes a multi-step form feel short.
 */
export function OnboardingProgress({
  steps,
  current,
}: {
  steps: readonly WizardStep[];
  current: number;
}) {
  const pct = ((current + 1) / steps.length) * 100;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Step {current + 1} of {steps.length}
        </p>
        <p className="text-xs text-muted-foreground">
          {Math.round(pct)}% complete
        </p>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="flex flex-wrap gap-x-6 gap-y-2">
        {steps.map((step, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li
              key={step.id}
              className={cn(
                "flex items-center gap-2 text-xs",
                active
                  ? "font-semibold text-foreground"
                  : done
                    ? "text-muted-foreground"
                    : "text-muted-foreground",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-meta font-bold",
                  done
                    ? "bg-success text-success-foreground"
                    : active
                      ? "bg-primary text-primary-foreground"
                      : "border border-dashed border-border",
                )}
              >
                {done ? <Check className="size-3" strokeWidth={3} /> : i + 1}
              </span>
              {step.title}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
