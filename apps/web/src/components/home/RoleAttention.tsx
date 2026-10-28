"use client";

import { useCallback } from "react";
import {
  ClipboardCheck,
  Gavel,
  ListChecks,
  ShieldAlert,
  Trophy,
} from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { AttentionCard } from "@/components/common/AttentionCard";
import { Metric, MetricGrid } from "@/components/common/Metric";
import { SectionError } from "@/components/common/SectionError";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  fetchFraudReviewQueue,
  fetchHiringFunnel,
  fetchJudgingQueue,
  fetchMyApplications,
  fetchMyAssessments,
  fetchMyHackathons,
} from "@/lib/api";

/** Placeholder sized to the real card, so the hub doesn't reflow when counts land. */
function AttentionSkeleton() {
  return <Skeleton className="h-17 w-full rounded-lg" />;
}

/** Shared plumbing: every role's attention block is "fetch one list, count what's
 * outstanding, offer the action". */
function useRoleResource<T>(
  fetcher: (token: string) => Promise<T>,
  cacheKey: string,
) {
  const { getToken } = useAuth();
  const run = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetcher(token);
  }, [getToken, fetcher]);
  return useAsyncResource(run, cacheKey);
}

export function JudgeAttention() {
  const { data, error, loading, retry } = useRoleResource(
    fetchJudgingQueue,
    "hub:judge",
  );

  if (error && !data)
    return <SectionError message={error} onRetry={retry} retrying={loading} />;
  if (!data) return <AttentionSkeleton />;

  const unscored = data.filter((entry) => entry.judge_score === null).length;
  const scored = data.length - unscored;

  return (
    <div className="space-y-3">
      <AttentionCard
        count={unscored}
        noun="submission"
        verb="awaiting your score"
        href="/evaluations"
        actionLabel={unscored > 0 ? "Start scoring" : "View queue"}
        icon={Gavel}
        clearedLabel="Every submission has been scored"
      />
      {data.length > 0 ? (
        <MetricGrid className="lg:grid-cols-2">
          <Metric label="Scored by you" value={scored} href="/evaluations" />
          <Metric
            label="Total in queue"
            value={data.length}
            href="/evaluations"
          />
        </MetricGrid>
      ) : null}
    </div>
  );
}

export function AdminAttention() {
  const { data, error, loading, retry } = useRoleResource(
    fetchFraudReviewQueue,
    "hub:admin",
  );

  if (error && !data)
    return <SectionError message={error} onRetry={retry} retrying={loading} />;
  if (!data) return <AttentionSkeleton />;

  // A disputed flag has a candidate waiting on a human decision, so it outranks the
  // rest of the queue rather than being one undifferentiated row in it.
  const disputed = data.filter((entry) => entry.has_dispute).length;

  return (
    <div className="space-y-3">
      <AttentionCard
        count={data.length}
        noun="flag"
        verb="awaiting review"
        href="/fraud-review"
        actionLabel={data.length > 0 ? "Review flags" : "Open queue"}
        icon={ShieldAlert}
        clearedLabel="No flags awaiting review"
      />
      {data.length > 0 ? (
        <MetricGrid className="lg:grid-cols-2">
          <Metric
            label="With a candidate dispute"
            value={disputed}
            hint={
              disputed > 0 ? "A candidate is waiting on a decision" : undefined
            }
            href="/fraud-review"
          />
          <Metric label="Total open" value={data.length} href="/fraud-review" />
        </MetricGrid>
      ) : null}
    </div>
  );
}

export function RecruiterAttention() {
  const funnel = useRoleResource(fetchHiringFunnel, "hub:recruiter:funnel");

  if (funnel.error && !funnel.data) {
    return (
      <SectionError
        message={funnel.error}
        onRetry={funnel.retry}
        retrying={funnel.loading}
      />
    );
  }
  if (!funnel.data) return <AttentionSkeleton />;

  const stages = funnel.data.stages ?? [];
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  const byStage = (name: string) =>
    stages.find((stage) => stage.stage === name)?.count ?? 0;

  return (
    <div className="space-y-3">
      <AttentionCard
        count={byStage("sourced")}
        noun="applicant"
        verb="not yet screened"
        href="/job-postings"
        actionLabel={byStage("sourced") > 0 ? "Open pipelines" : "View jobs"}
        icon={ListChecks}
        clearedLabel="Every applicant has been screened"
      />
      {total > 0 ? (
        <MetricGrid>
          <Metric label="In pipeline" value={total} href="/job-postings" />
          <Metric
            label="Screened"
            value={byStage("screened")}
            href="/job-postings"
          />
          <Metric
            label="Interviewing"
            value={byStage("interview_scheduled")}
            href="/job-postings"
          />
          <Metric
            label="Offered"
            value={byStage("offered")}
            href="/job-postings"
          />
        </MetricGrid>
      ) : null}
    </div>
  );
}

export function OrganizerAttention() {
  const { data, error, loading, retry } = useRoleResource(
    fetchMyHackathons,
    "hub:organizer",
  );

  if (error && !data)
    return <SectionError message={error} onRetry={retry} retrying={loading} />;
  if (!data) return <AttentionSkeleton />;

  // There is no "submissions awaiting judging" endpoint, so the hub reports event
  // status rather than inventing a number it cannot source. "judging" is the state
  // that actually wants the organizer's attention — it ends with finalizing rankings.
  const active = data.filter((event) => event.status === "active").length;
  const judging = data.filter((event) => event.status === "judging").length;
  const draft = data.filter((event) => event.status === "draft").length;

  return (
    <div className="space-y-3">
      <AttentionCard
        count={active}
        noun="event"
        verb="currently running"
        href="/events"
        actionLabel={data.length > 0 ? "Manage events" : "Create an event"}
        icon={Trophy}
        clearedLabel={
          data.length > 0 ? "No events are running right now" : "No events yet"
        }
      />
      {data.length > 0 ? (
        <MetricGrid>
          <Metric label="All events" value={data.length} href="/events" />
          <Metric label="Active" value={active} href="/events" />
          <Metric
            label="In judging"
            value={judging}
            hint={judging > 0 ? "Ready to finalize rankings" : undefined}
            href="/events"
          />
          <Metric label="Draft" value={draft} href="/events" />
        </MetricGrid>
      ) : null}
    </div>
  );
}

export function CandidateAttention() {
  const applications = useRoleResource(
    fetchMyApplications,
    "hub:candidate:applications",
  );
  const assessments = useRoleResource(
    fetchMyAssessments,
    "hub:candidate:assessments",
  );

  if (!applications.data && !assessments.data) {
    if (applications.error) {
      return (
        <SectionError
          message={applications.error}
          onRetry={applications.retry}
          retrying={applications.loading}
        />
      );
    }
    return <AttentionSkeleton />;
  }

  const apps = applications.data ?? [];
  const pending = assessments.data?.length ?? 0;
  const live = apps.filter(
    (application) =>
      application.stage !== "rejected" && application.stage !== "hired",
  ).length;

  return (
    <div className="space-y-3">
      {pending > 0 ? (
        <AttentionCard
          count={pending}
          noun="assessment"
          verb="waiting for you"
          href="/assessments"
          actionLabel="Start"
          icon={ClipboardCheck}
        />
      ) : null}
      {apps.length > 0 ? (
        <MetricGrid className="lg:grid-cols-3">
          <Metric
            label="Applications"
            value={apps.length}
            href="/applications"
          />
          <Metric label="Still in play" value={live} href="/applications" />
          <Metric
            label="Offers"
            value={
              apps.filter((application) => application.stage === "offered")
                .length
            }
            href="/applications"
          />
        </MetricGrid>
      ) : null}
    </div>
  );
}
