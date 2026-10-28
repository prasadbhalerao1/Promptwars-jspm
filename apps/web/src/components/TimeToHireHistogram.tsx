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

import type { TimeToHireResponse } from "@/lib/api";

export function TimeToHireHistogram({
  timeToHire,
}: {
  timeToHire: TimeToHireResponse;
}) {
  const data = Object.entries(timeToHire.distribution).map(
    ([bucket, count]) => ({ bucket, count }),
  );

  if (data.every((d) => d.count === 0)) {
    return (
      <p className="text-sm text-muted-foreground">
        No hires yet - time-to-hire populates once candidates reach the
        &quot;Hired&quot; stage.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
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
      {timeToHire.median_days !== null && (
        <p className="text-xs text-muted-foreground">
          Median time to hire: {timeToHire.median_days.toFixed(1)} days
        </p>
      )}
    </div>
  );
}
