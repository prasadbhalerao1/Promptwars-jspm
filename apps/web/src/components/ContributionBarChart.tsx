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

import type { ContributionReportResponse } from "@/lib/api";

export function ContributionBarChart({
  reports,
}: {
  reports: ContributionReportResponse[];
}) {
  const data = reports.map((r) => ({
    member: r.github_username ?? "unknown",
    share: Math.round((r.contribution_share ?? 0) * 100),
  }));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="member" tick={{ fontSize: 11 }} />
          <YAxis unit="%" tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar
            dataKey="share"
            fill="var(--color-primary)"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
