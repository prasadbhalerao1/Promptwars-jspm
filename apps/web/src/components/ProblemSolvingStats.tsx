"use client";

import { useMemo } from "react";
import {
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ContributionHeatmap } from "@/components/charts/ContributionHeatmap";
import { Metric, MetricGrid } from "@/components/common/Metric";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeetcodeStats } from "@/lib/api";
import { ChartTooltipContent } from "@/components/ui/chart";

interface ProblemSolvingStatsProps {
  leetcodeUsername: string | null;
  leetcodeStats: LeetcodeStats | null;
}

// Difficulty is an ordered scale, so it reads off the chart ramp rather than three
// unrelated hexes — and stays legible against the rest of the product's charts.
const DIFFICULTY_COLORS: Record<string, string> = {
  Easy: "var(--chart-1)",
  Medium: "var(--chart-3)",
  Hard: "var(--chart-4)",
};

interface RatingPayload {
  value: number;
  payload: {
    contest: string;
    rating: number;
  };
}

interface CustomLineTooltipProps {
  active?: boolean;
  payload?: RatingPayload[];
}

interface DifficultyPayload {
  name: string;
  value: number;
}

const DifficultyTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: DifficultyPayload[];
}) => {
  if (!active || !payload?.length) return null;
  const slice = payload[0];
  return (
    <ChartTooltipContent
      rows={[
        {
          label: slice.name,
          value: String(slice.value),
          color: DIFFICULTY_COLORS[slice.name],
        },
      ]}
    />
  );
};

const CustomLineTooltip = ({ active, payload }: CustomLineTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <ChartTooltipContent
        title={payload[0].payload.contest}
        rows={[
          {
            label: "Rating",
            value: String(payload[0].value),
            color: "var(--chart-1)",
          },
        ]}
      />
    );
  }
  return null;
};

export function ProblemSolvingStats({
  leetcodeUsername,
  leetcodeStats,
}: ProblemSolvingStatsProps) {
  const calendarDays = useMemo(() => {
    if (!leetcodeStats) return [];
    return Object.entries(leetcodeStats.submission_calendar).map(
      ([unixSeconds, count]) => ({
        date: new Date(Number(unixSeconds) * 1000).toISOString().slice(0, 10),
        count,
      }),
    );
  }, [leetcodeStats]);

  const difficultyData = useMemo(() => {
    if (!leetcodeStats) return [];
    return [
      { name: "Easy", value: leetcodeStats.easy_solved },
      { name: "Medium", value: leetcodeStats.medium_solved },
      { name: "Hard", value: leetcodeStats.hard_solved },
    ];
  }, [leetcodeStats]);

  const ratingData = useMemo(() => {
    if (!leetcodeStats) return [];
    return leetcodeStats.contest_history.map((point) => ({
      contest: point.title,
      rating: Math.round(point.rating),
    }));
  }, [leetcodeStats]);

  if (!leetcodeUsername) {
    return (
      <Card>
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="text-section font-semibold text-foreground">
            Problem Solving Stats
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">
            Connect LeetCode to show your problem-solving activity here.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!leetcodeStats) {
    return (
      <Card>
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="text-section font-semibold text-foreground">
            Problem Solving Stats
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">
            Stats haven&apos;t synced yet - try refreshing.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3 border-b border-border mb-4 flex-row items-center justify-between">
        <div>
          <CardTitle className="text-section font-semibold text-foreground">
            Problem Solving Stats
          </CardTitle>
          <p className="text-meta text-muted-foreground mt-0.5">
            @{leetcodeUsername} on LeetCode
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-6 pt-0">
        <MetricGrid>
          <Metric label="Questions solved" value={leetcodeStats.total_solved} />
          <Metric label="Active days" value={leetcodeStats.total_active_days} />
          <Metric label="Current streak" value={leetcodeStats.current_streak} />
          <Metric
            label="Global rank"
            value={
              leetcodeStats.ranking !== null
                ? leetcodeStats.ranking.toLocaleString("en-US")
                : "Unranked"
            }
          />
        </MetricGrid>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div className="p-4 rounded-xl bg-muted/40">
            <p className="mb-2 text-meta font-medium text-muted-foreground">
              Question Distribution
            </p>
            <div className="h-44 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={difficultyData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={45}
                    outerRadius={65}
                    stroke="none"
                  >
                    {difficultyData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={DIFFICULTY_COLORS[entry.name]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<DifficultyTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {ratingData.length > 1 && (
            <div className="p-4 rounded-xl bg-muted/40">
              <p className="mb-2 text-meta font-medium text-muted-foreground">
                Contest Rating
              </p>
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={ratingData}
                    margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
                  >
                    <XAxis dataKey="contest" tick={false} axisLine={false} />
                    <YAxis
                      tick={{
                        fontSize: 10,
                        fill: "var(--muted-foreground)",
                        fontFamily: "monospace",
                      }}
                      tickLine={false}
                      axisLine={false}
                      domain={["dataMin - 50", "dataMax + 50"]}
                    />
                    <Tooltip content={<CustomLineTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="rating"
                      stroke="var(--chart-1)"
                      strokeWidth={2.5}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>


      </CardContent>
    </Card>
  );
}
