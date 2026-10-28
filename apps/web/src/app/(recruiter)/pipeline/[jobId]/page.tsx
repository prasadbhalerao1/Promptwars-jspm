"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Users } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { KanbanBoard } from "@/components/KanbanBoard";
import { KanbanSkeleton } from "@/components/KanbanSkeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  fetchApplications,
  fetchJobs,
  updateApplicationStage,
  type ApplicationStage,
  type ApplicationWithCandidateResponse,
} from "@/lib/api";

export default function RecruiterPipelinePage() {
  const params = useParams<{ jobId: string }>();
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchApplications(token, { jobId: params.jobId });
  }, [getToken, params.jobId]);

  // There is no single-job endpoint, and the applications payload carries the
  // candidate but not the job. Resolving the title from the recruiter's own job list
  // is one cached request, and without it this page never names the role it manages.
  const jobFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchJobs(token);
  }, [getToken]);
  const { data: jobs } = useAsyncResource(jobFetcher, "recruiter:jobs");
  const jobTitle = jobs?.find((job) => job.id === params.jobId)?.title ?? null;
  // useAsyncResource owns the mount-fetch + cancellation-on-unmount pattern — previously
  // duplicated by hand between a useEffect body and a separate load() callback, which
  // fired the same request twice on mount.
  const {
    data: fetchedApplications,
    error: fetchError,
    retry,
  } = useAsyncResource(fetcher, `pipeline:${params.jobId}`);

  // Local override so optimistic drag updates apply instantly on top of the fetched
  // data. Reset during render (not in an effect — see React's "adjusting state during
  // render" pattern) whenever a fresh fetch result lands, identified by that array's
  // identity changing; retry() only bumps a tick and returns before the refetch
  // resolves, so clearing the override eagerly on the retry() call itself would flash
  // the stale pre-drag state back in for the gap until the new fetch actually lands.
  const [override, setOverride] = useState<
    ApplicationWithCandidateResponse[] | null
  >(null);
  const [stageError, setStageError] = useState<string | null>(null);
  const [lastSeenFetched, setLastSeenFetched] = useState(fetchedApplications);
  if (fetchedApplications !== lastSeenFetched) {
    setLastSeenFetched(fetchedApplications);
    setOverride(null);
  }
  const applications = override ?? fetchedApplications;
  const error = stageError ?? fetchError;

  async function handleStageChange(
    applicationId: string,
    nextStage: ApplicationStage,
  ) {
    setOverride(
      (applications ?? []).map((a) =>
        a.id === applicationId ? { ...a, stage: nextStage } : a,
      ),
    );
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await updateApplicationStage(token, applicationId, nextStage);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update stage";
      setStageError(message);
      // The card visibly snaps back on rollback, which needs explaining — this is
      // exactly the case a toast is for.
      toast.error(message);
      // Roll back the optimistic update by re-syncing from the server — on success the
      // optimistic state already matches, so no refetch is needed there.
      retry();
    }
  }

  return (
    <Page width="wide">
      <PageHeader
        // The page previously announced itself as "Applicant Tracking (ATS) Pipeline"
        // and showed no job context at all, so a recruiter deep in /pipeline/[jobId]
        // could not tell which role they were looking at.
        title={jobTitle ?? "Pipeline"}
        description="Drag a candidate between columns to move them through your hiring stages."
        breadcrumb={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/job-postings" />}>
                  My jobs
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Pipeline</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
      />

      {error ? (
        <SectionError message={error} onRetry={retry} retrying={false} />
      ) : null}
      {applications === null && !error && <KanbanSkeleton />}
      {applications !== null && applications.length === 0 && (
        <EmptyState
          icon={Users}
          title="No applications yet"
          description="Candidates who apply to this role will appear here, and you can move them through your stages."
        />
      )}
      {applications !== null && applications.length > 0 && (
        <KanbanBoard
          applications={applications}
          onStageChange={handleStageChange}
        />
      )}
      {/* A "Pipeline Stages" card used to sit here spelling out the raw enum
          (`interview_scheduled`) and explaining that you can drag cards. The board
          already shows the stages as its own column headers, so the card restated
          the UI in database vocabulary. */}
    </Page>
  );
}
