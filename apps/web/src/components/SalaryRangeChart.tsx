"use client";

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// doc/SRS/01 §8 names a "salary range chart" on the career page. A floating bar
// (rendered as a stacked bar: an invisible offset segment up to `low`, then a visible
// segment from `low` to `high`) is the standard recharts pattern for a range/interval,
// since recharts has no first-class range-bar primitive.
export function SalaryRangeChart({ low, high }: { low: number; high: number }) {
  const data = [{ name: "Estimated range", offset: low, range: high - low }];
  const axisMax = Math.ceil((high * 1.15) / 10_000) * 10_000;

  const formatUsd = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);

  return (
    <div className="h-24 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, bottom: 8, left: 16 }}
        >
          <XAxis
            type="number"
            domain={[0, axisMax]}
            tickFormatter={formatUsd}
            tick={{ fontSize: 11 }}
          />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip
            formatter={(_value, key) =>
              key === "range"
                ? [`${formatUsd(low)} - ${formatUsd(high)}`, "Estimated range"]
                : ["", ""]
            }
          />
          <Bar
            dataKey="offset"
            stackId="range"
            fill="transparent"
            isAnimationActive={false}
          />
          <Bar
            dataKey="range"
            stackId="range"
            fill="var(--color-primary)"
            radius={4}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
