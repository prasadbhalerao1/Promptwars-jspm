"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { APPLICATION_STAGE_LABELS, type HiringFunnelResponse } from "@/lib/api";

export function FunnelChart({ funnel }: { funnel: HiringFunnelResponse }) {
  const data = funnel.stages.map((s) => ({
    stage: APPLICATION_STAGE_LABELS[s.stage],
    count: s.count,
  }));

  if (funnel.stages.every((s) => s.count === 0)) {
    return (
      <p className="text-sm text-muted-foreground">
        No applications yet - the funnel will populate once candidates apply or
        are sourced.
      </p>
    );
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="stage"
            tick={{ fontSize: 10 }}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar
            dataKey="count"
            fill="var(--color-primary)"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
