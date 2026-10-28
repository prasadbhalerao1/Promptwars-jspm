"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/common/EmptyState";
import {
  CHART_CURSOR,
  CHART_TICK,
  ChartTooltipContent,
} from "@/components/ui/chart";

interface TooltipPayload {
  value: number;
  payload: {
    week: number;
    commits: number;
  };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <ChartTooltipContent
        title={`Week ${payload[0].payload.week}`}
        rows={[
          {
            label: "Commits",
            value: String(payload[0].value),
            color: "var(--chart-1)",
          },
        ]}
      />
    );
  }
  return null;
};

export interface CommitActivityChartProps {
  weeklyCounts: number[] | undefined;
}

export function CommitActivityChart({
  weeklyCounts,
}: CommitActivityChartProps) {
  const data = useMemo(
    () =>
      (weeklyCounts ?? []).map((count, i) => ({ week: i + 1, commits: count })),
    [weeklyCounts],
  );

  if (data.length === 0) {
    return (
      <EmptyState
        title="No commit activity yet"
        description="Activity appears here once your GitHub data has finished syncing."
      />
    );
  }

  return (
    <div className="h-48 w-full select-none pt-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
        >
          <XAxis dataKey="week" tick={false} axisLine={false} />
          <YAxis
            tick={CHART_TICK}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={CHART_CURSOR}
          />
          <Bar
            dataKey="commits"
            fill="var(--chart-1)"
            radius={[3, 3, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
