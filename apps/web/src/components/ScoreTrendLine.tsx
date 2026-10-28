import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TalentScoreResponse } from "@/lib/api";
import { ChartTooltipContent } from "@/components/ui/chart";

interface TooltipPayload {
  value: number;
  payload: {
    date: string;
    overall: number;
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
        title={payload[0].payload.date}
        rows={[
          {
            label: "Score",
            value: payload[0].value.toFixed(1),
            color: "var(--chart-1)",
          },
        ]}
      />
    );
  }
  return null;
};

export function ScoreTrendLine({
  history,
}: {
  history: TalentScoreResponse[];
}) {
  const data = history.map((s) => ({
    date: new Date(s.computed_at).toLocaleDateString(),
    overall: s.overall,
  }));

  if (data.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">
        Score history will appear here once your Talent Score has been
        recomputed a few times.
      </p>
    );
  }

  return (
    <div className="h-56 w-full pt-2 select-none">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
        >
          <XAxis
            dataKey="date"
            tick={{
              fontSize: 10,
              fill: "var(--muted-foreground)",
              fontFamily: "monospace",
            }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{
              fontSize: 10,
              fill: "var(--muted-foreground)",
              fontFamily: "monospace",
            }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="overall"
            stroke="var(--chart-1)"
            strokeWidth={2.5}
            dot={{
              r: 4,
              fill: "var(--chart-1)",
              stroke: "var(--popover)",
              strokeWidth: 1.5,
            }}
            activeDot={{
              r: 6,
              fill: "var(--chart-1)",
              stroke: "var(--popover)",
              strokeWidth: 2,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
