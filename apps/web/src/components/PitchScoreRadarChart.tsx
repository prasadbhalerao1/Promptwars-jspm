"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { PITCH_SCORE_LABELS, type RubricScore } from "@/lib/api";

export function PitchScoreRadarChart({
  scores,
}: {
  scores: Record<string, RubricScore>;
}) {
  const data = Object.entries(PITCH_SCORE_LABELS).map(([key, label]) => ({
    subject: label,
    value: scores[key]?.value ?? 0,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Pitch Score"
            dataKey="value"
            stroke="var(--color-primary)"
            fill="var(--color-primary)"
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
