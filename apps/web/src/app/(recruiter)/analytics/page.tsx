"use client";

import { useCallback } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FunnelChart } from "@/components/FunnelChart";
import { TimeToHireHistogram } from "@/components/TimeToHireHistogram";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { Metric, MetricGrid } from "@/components/common/Metric";
import {
  fetchHiringFunnel,
  fetchSourceBreakdown,
  fetchTimeToHire,
} from "@/lib/api";

export default function RecruiterAnalyticsPage() {
  const { getToken } = useAuth();

  // Was a hand-rolled useEffect/useState triple, so this page alone had no retry
  // or backoff on a transient 502/503 — the three requests just failed silently
  // into one error string. useAsyncResource owns the fetch, retry and cancellation.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    const [funnel, timeToHire, sourceBreakdown] = await Promise.all([
      fetchHiringFunnel(token),
      fetchTimeToHire(token),
      fetchSourceBreakdown(token),
    ]);
    return { funnel, timeToHire, sourceBreakdown };
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "recruiter:analytics",
  );

  const funnel = data?.funnel ?? null;
  const timeToHire = data?.timeToHire ?? null;
  const sourceBreakdown = data?.sourceBreakdown ?? null;

  const totalSourced = sourceBreakdown
    ? sourceBreakdown.direct +
      sourceBreakdown.copilot_search +
      sourceBreakdown.hackathon
    : 0;
  const hiredCount =
    funnel?.stages.find((s) => s.stage === "hired")?.count ?? 0;
  const sourcedCount =
    funnel?.stages.find((s) => s.stage === "sourced")?.count ?? 0;

  const medianDays = timeToHire?.median_days;

  return (
    <Page>
      <PageHeader
        title="Analytics"
        description="Funnel conversion, time to hire, and where your candidates come from - across all your job postings."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}

      <MetricGrid>
        <Metric label="Total applications" value={sourcedCount} />
        <Metric label="Hired" value={hiredCount} />
        <Metric
          label="Median time to hire"
          // `median_days` is legitimately null until something has actually been
          // hired — reported as "not yet computable", never as a zero.
          value={
            medianDays === null || medianDays === undefined
              ? "Not recorded"
              : `${medianDays.toFixed(0)}d`
          }
          hint={
            medianDays === null || medianDays === undefined
              ? "No hires yet"
              : undefined
          }
        />
        <Metric
          label="Copilot-sourced"
          value={
            totalSourced > 0
              ? `${Math.round((100 * (sourceBreakdown?.copilot_search ?? 0)) / totalSourced)}%`
              : "Not recorded"
          }
        />
      </MetricGrid>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Hiring funnel
            </CardTitle>
            <CardDescription>
              Conversion from sourced through hired.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {funnel ? (
              <FunnelChart funnel={funnel} />
            ) : (
              <Skeleton className="h-56 w-full" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Time to hire
            </CardTitle>
            <CardDescription>
              Days from application to the hired stage.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {timeToHire ? (
              <TimeToHireHistogram timeToHire={timeToHire} />
            ) : (
              <Skeleton className="h-56 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Source of hire
          </CardTitle>
          <CardDescription>
            Where the candidates in your pipeline came from.
          </CardDescription>
        </CardHeader>
        {/* Was a bare grid-cols-3 with no breakpoint: at 375px "Copilot Search"
            wrapped and the three columns collapsed into unreadable slivers. */}
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Metric label="Direct" value={sourceBreakdown?.direct ?? "Not recorded"} />
          <Metric
            label="Copilot search"
            value={sourceBreakdown?.copilot_search ?? "Not recorded"}
          />
          <Metric label="Hackathon" value={sourceBreakdown?.hackathon ?? "Not recorded"} />
        </CardContent>
      </Card>
    </Page>
  );
}
