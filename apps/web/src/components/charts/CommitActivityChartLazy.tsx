"use client";

import dynamic from "next/dynamic";

import type { CommitActivityChartProps } from "@/components/charts/CommitActivityChart";

/** Client wrapper that keeps recharts out of the public portfolio's initial payload.
 *
 * `/[username]` is a Server Component with a stated Lighthouse >= 90 target, and it
 * imported this chart statically — so every visitor downloaded recharts before the page
 * could become interactive, for one below-the-fold graph. A Server Component cannot call
 * `next/dynamic` with `ssr: false` itself, hence this thin client boundary.
 *
 * The fallback reserves the chart's real height, so deferring it costs no layout shift.
 */
const CommitActivityChart = dynamic(
  () =>
    import("@/components/charts/CommitActivityChart").then(
      (m) => m.CommitActivityChart,
    ),
  {
    ssr: false,
    loading: () => <div className="h-56 animate-pulse rounded-md bg-muted" />,
  },
);

export function CommitActivityChartLazy(props: CommitActivityChartProps) {
  return <CommitActivityChart {...props} />;
}
