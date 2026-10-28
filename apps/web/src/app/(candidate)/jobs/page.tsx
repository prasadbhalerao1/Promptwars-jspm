"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Briefcase } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { applyToJob, fetchOpenJobs, fetchMyApplications } from "@/lib/api";

// Candidates browse via `GET /jobs/open`; the plain `GET /jobs` is recruiter-scoped
// and 403s a candidate token.
export default function CandidateJobsPage() {
  const { getToken } = useAuth();
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");

    // Both requests are independent, so they go out together. Awaiting applications
    // first put two full round trips in series for no reason.
    //
    // `fetchMyApplications` keeps its own catch: a failure there should still leave
    // the job list usable, just without "already applied" markers. `fetchOpenJobs`
    // rejecting is a real error and propagates to the resource's error state.
    const [applications, jobs] = await Promise.all([
      fetchMyApplications(token).catch(() => []),
      fetchOpenJobs(token),
    ]);
    return { jobs, appliedIds: new Set(applications.map((a) => a.job_id)) };
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "candidate:open-jobs",
  );

  const jobs = data?.jobs ?? [];
  // Server truth, plus anything applied to in this session.
  const appliedIds = new Set([...(data?.appliedIds ?? []), ...applied]);

  async function handleApply(jobId: string, title: string) {
    setBusyJobId(jobId);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await applyToJob(token, jobId);
      setApplied((prev) => new Set(prev).add(jobId));
      toast.success(`Applied to ${title}`, {
        description: "Track it on your Applications page.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to apply";
      // Was rendered as a per-job inline string, which meant the raw
      // `already_applied` API error code could surface verbatim at the candidate.
      if (message.includes("already_applied")) {
        setApplied((prev) => new Set(prev).add(jobId));
        toast.info(`You have already applied to ${title}`);
      } else {
        toast.error(message);
      }
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <Page>
      <PageHeader
        title="Jobs"
        description="Open roles you can apply to. Everything you apply for is tracked on your Applications page."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !data ? <CardListSkeleton /> : null}

      {data && jobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No open roles right now"
          description="New postings appear here as recruiters publish them."
        />
      ) : null}

      {jobs.length > 0 && (
        <ul className="space-y-3">
          {jobs.map((job) => {
            const hasApplied = appliedIds.has(job.id);
            return (
              <li key={job.id} className="rounded-xl p-4 shadow-flat">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-section font-semibold text-foreground">
                      {job.title}
                    </h2>
                    <p className="mt-0.5 text-meta text-muted-foreground">
                      {job.location ??
                        (job.is_remote ? "Remote" : "Location not specified")}
                      {job.is_remote && job.location ? " · Remote" : ""}
                      {job.min_experience_years != null
                        ? ` · ${job.min_experience_years}+ yrs experience`
                        : ""}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant={hasApplied ? "outline" : "default"}
                    disabled={hasApplied}
                    pending={busyJobId === job.id}
                    onClick={() => handleApply(job.id, job.title)}
                  >
                    {hasApplied
                      ? "Applied"
                      : busyJobId === job.id
                        ? "Applying…"
                        : "Apply"}
                  </Button>
                </div>

                <p className="mt-3 text-body leading-relaxed whitespace-pre-line text-muted-foreground">
                  {job.description}
                </p>

                {job.required_skills && job.required_skills.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {job.required_skills.map((skill) => (
                      <Badge key={skill} variant="outline">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Page>
  );
}
