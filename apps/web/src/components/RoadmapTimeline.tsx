"use client";

import { Badge } from "@/components/ui/badge";
import type { RoadmapStage } from "@/lib/api";

// doc/SRS/01 §8 explicitly names this component ("RoadmapTimeline.tsx") — FR-4.3's
// staged roadmap (stages -> skills -> estimated timeline) rendered as a vertical
// timeline, ordered stage-by-stage.
export function RoadmapTimeline({ stages }: { stages: RoadmapStage[] }) {
  if (stages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing to roadmap - no significant skill gaps for this role.
      </p>
    );
  }

  return (
    <ol className="space-y-4">
      {stages.map((stage, i) => (
        <li
          key={`${stage.stage}-${i}`}
          className="relative border-l-2 border-border pl-4"
        >
          <span className="absolute -left-[7px] top-1 size-3 rounded-full bg-primary" />
          <p className="text-sm font-medium">
            {i + 1}. {stage.stage}{" "}
            <span className="font-normal text-muted-foreground">
              (~{stage.estimated_weeks} wk)
            </span>
          </p>
          {stage.description && (
            <p className="text-xs text-muted-foreground">{stage.description}</p>
          )}
          <div className="mt-1 flex flex-wrap gap-1">
            {stage.skills.map((skill) => (
              <Badge key={skill} variant="secondary">
                {skill}
              </Badge>
            ))}
          </div>
        </li>
      ))}
    </ol>
  );
}
