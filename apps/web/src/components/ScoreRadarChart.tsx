"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { SUB_SCORE_LABELS, type SubScore } from "@/lib/api";

/** Rim labels, shortened.
 *
 * The full names ("Open Source Contributions", "Community Participation") are what the
 * sub-score list beside this chart shows, but on a radar rim they are wider than the
 * space either side of the plot and get clipped by the container - and padding the
 * margin to fit them shrinks the polygon until the shape itself is unreadable. The
 * chart carries the shape; the list carries the full names and the numbers. */
const AXIS_LABELS: Record<string, string> = {
  coding_ability: "Coding",
  problem_solving: "Problem solving",
  project_quality: "Project quality",
  innovation: "Innovation",
  technical_consistency: "Consistency",
  community_participation: "Community",
  leadership: "Leadership",
  open_source_contributions: "Open source",
  hackathon_performance: "Hackathons",
  verified_credentials: "Credentials",
};

export function ScoreRadarChart({
  subScores,
}: {
  subScores: Record<string, SubScore>;
}) {
  // Only plot dimensions this score actually has.
  //
  // This mapped the full label catalogue and fell back to `value: 0` for anything
  // missing, so a candidate scored on seven dimensions got a nine-axis chart whose
  // polygon collapsed to the centre on the two they were never measured on. That reads
  // as "scored zero" when the truth is "not measured" - the exact misreading the
  // evidence model exists to prevent - and it disagreed with the sub-score list
  // rendered directly beside it.
  const data = Object.entries(SUB_SCORE_LABELS)
    .filter(([key]) => typeof subScores[key]?.value === "number")
    .map(([key, label]) => ({
      subject: AXIS_LABELS[key] ?? label,
      value: subScores[key]!.value as number,
    }));

  return (
    <div className="h-64 w-full sm:h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart
          data={data}
          margin={{ top: 16, right: 56, bottom: 16, left: 56 }}
        >
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fontSize: 10, fill: "var(--foreground)", fontWeight: 500 }}
          />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Talent Score"
            dataKey="value"
            stroke="var(--chart-1)"
            fill="var(--chart-1)"
            fillOpacity={0.18}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
