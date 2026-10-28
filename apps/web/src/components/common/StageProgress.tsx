"use client";

import { CheckIcon, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * Stepwise progress for a long-running backend pipeline.
 *
 * Progress is driven by `currentStage`, a real label the backend writes as each pipeline
 * node completes. Includes smooth micro-animations and clear active indicators.
 */
export function StageProgress({
  stages,
  currentStage,
  className,
}: {
  /** Ordered phase labels, matching the strings the backend reports. */
  stages: readonly string[];
  /** The phase currently running, or null/undefined before the first is reported. */
  currentStage?: string | null;
  className?: string;
}) {
  const activeIndex = currentStage ? stages.indexOf(currentStage) : -1;
  const unknownStage = Boolean(currentStage) && activeIndex === -1;

  return (
    <div
      className={cn("space-y-2.5", className)}
      aria-live="polite"
      aria-busy="true"
    >
      {stages.map((stage, i) => {
        const done = activeIndex > i;
        const active = activeIndex === i;
        return (
          <motion.div
            key={stage}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.04 }}
            className="flex items-center gap-2.5 text-sm"
          >
            <span
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-full border transition-all duration-300",
                done && "border-success bg-success text-success-foreground shadow-xs",
                active && "border-primary bg-primary/10 text-primary ring-2 ring-primary/20",
                !done && !active && "border-muted-foreground/30 bg-muted/20 text-muted-foreground",
              )}
            >
              {done ? (
                <CheckIcon className="size-3" strokeWidth={3} aria-hidden />
              ) : active ? (
                <Loader2 className="size-3 animate-spin text-primary" />
              ) : (
                <span className="size-1.5 rounded-full bg-muted-foreground/40" />
              )}
            </span>
            <span
              className={cn(
                "transition-colors duration-200",
                done && "font-medium text-foreground",
                active && "font-semibold text-primary",
                !done && !active && "text-muted-foreground/70",
              )}
            >
              {stage}
            </span>
            {done ? (
              <span className="ml-auto text-xs text-success font-medium select-none">
                Completed
              </span>
            ) : active ? (
              <span className="ml-auto flex items-center gap-1.5 text-xs text-primary font-medium select-none">
                <span className="size-1.5 rounded-full bg-primary animate-ping" />
                In progress
              </span>
            ) : null}
          </motion.div>
        );
      })}
      {unknownStage ? (
        <div className="flex items-center gap-2.5 text-sm">
          <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-primary bg-primary/10 text-primary">
            <Loader2 className="size-3 animate-spin text-primary" />
          </span>
          <span className="font-semibold text-primary">{currentStage}</span>
        </div>
      ) : null}
    </div>
  );
}

/** Full phase labels for candidate ingestion when all sources are present. */
export const INGESTION_STAGES = [
  "Reading your resume",
  "Analyzing your GitHub repositories",
  "Reading your certificates",
  "Merging your profile",
  "Computing your Talent Score",
  "Awarding badges",
] as const;

/** GitHub-specific ingestion stages when only GitHub is being connected/synced. */
export const GITHUB_INGESTION_STAGES = [
  "Analyzing your GitHub repositories",
  "Merging your profile",
  "Computing your Talent Score",
  "Awarding badges",
] as const;
