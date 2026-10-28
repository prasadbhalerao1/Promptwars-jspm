"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Code2 } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import type { GithubProjectSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

// The categorical ramp, in order. Every entry is a distinct hue: the previous list
// repeated `bg-warning`, so the 3rd and 6th language rendered identically.
const LANGUAGE_COLORS = [
  "bg-chart-1",
  "bg-chart-2",
  "bg-chart-3",
  "bg-chart-4",
  "bg-chart-5",
];

function useLanguageBreakdown(projects: GithubProjectSummary[]) {
  return useMemo(() => {
    const totals = new Map<string, number>();
    for (const project of projects) {
      if (!project.languages) continue;
      for (const [lang, bytes] of Object.entries(project.languages)) {
        totals.set(
          lang,
          (totals.get(lang) ?? 0) + (typeof bytes === "number" ? bytes : 0),
        );
      }
    }
    const sum = [...totals.values()].reduce((a, b) => a + b, 0);
    return [...totals.entries()]
      .sort((a, b) => b[1] - a[1])
      // Capped at the ramp length: a 6th slice would wrap the modulo and repeat the
      // first colour, which is the duplicate-colour bug this ramp exists to avoid.
      .slice(0, LANGUAGE_COLORS.length)
      .map(([name, bytes], i) => ({
        name,
        percent: sum > 0 ? Math.round((bytes / sum) * 1000) / 10 : 0,
        color: LANGUAGE_COLORS[i],
      }));
  }, [projects]);
}

export function LanguageChart({
  projects,
}: {
  projects: GithubProjectSummary[];
}) {
  const languages = useLanguageBreakdown(projects);

  if (languages.length === 0) {
    return (
      <EmptyState
        icon={Code2}
        title="No language data yet"
        description="Language breakdown appears once your GitHub repositories have been analyzed."
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* Horizontal Stacked Bar */}
      <div className="flex h-3.5 w-full overflow-hidden rounded-full bg-muted p-[2px] border border-border/80">
        {languages.map((lang) => (
          <motion.div
            key={lang.name}
            initial={{ width: 0 }}
            animate={{ width: `${lang.percent}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className={cn(
              "h-full first:rounded-l-full last:rounded-r-full",
              lang.color,
            )}
            title={`${lang.name}: ${lang.percent}%`}
          />
        ))}
      </div>

      {/* Language Breakdown Grid */}
      <div className="grid grid-cols-2 gap-3">
        {languages.map((lang, idx) => (
          <motion.div
            key={lang.name}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05, duration: 0.2 }}
            className="flex items-center justify-between p-2.5 rounded-lg bg-card/50 border border-border/60 hover:border-border hover:bg-card transition-colors"
          >
            <div className="flex items-center gap-2">
              <span
                className={cn("h-2.5 w-2.5 rounded-full shrink-0", lang.color)}
              />
              <span className="font-semibold text-foreground text-xs">
                {lang.name}
              </span>
            </div>
            <span className="font-mono text-xs text-muted-foreground font-medium">
              {lang.percent}%
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
