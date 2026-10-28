"use client";

import { Page, PageHeader } from "@/components/common/PageHeader";

import { useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchJobs } from "@/lib/api";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ListChecks } from "lucide-react";

export default function RecruiterJobsListPage() {
  const { getToken } = useAuth();
  const jobsFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchJobs(token);
  }, [getToken]);
  // cacheKey: revisiting this list after viewing a job's matches/pipeline shows the
  // last-loaded postings instantly instead of re-paying the backend round-trip.
  const { data: jobs, error } = useAsyncResource(
    jobsFetcher,
    "job-postings:list",
  );

  return (
    <Page>
      <PageHeader
        title="Job postings"
        description="Every role you've posted, with links straight to its matches and pipeline."
        actions={
          <Button render={<Link href="/jobs/new" />}>Post a job</Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Postings</CardTitle>
          <CardDescription>
            Click through to ranked matches or the kanban pipeline for any job.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {!error && jobs === null && <CardListSkeleton />}
          {jobs !== null && jobs.length === 0 && (
            <EmptyState
              icon={ListChecks}
              title="No jobs posted yet"
              description="Publish a role and TRACE ranks the candidate pool against it, with the evidence behind every match."
              action={
                <Button render={<Link href="/jobs/new" />}>Post a job</Button>
              }
            />
          )}
          {jobs?.map((job) => (
            <div
              key={job.id}
              className="p-4 border rounded-md flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card shadow-flat"
            >
              <div>
                <h4 className="text-sm font-semibold text-foreground">
                  {job.title}
                </h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {job.location ?? "Remote / unspecified"} · Posted{" "}
                  {new Date(job.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  render={<Link href={`/jobs/${job.id}/matches`} />}
                  variant="outline"
                  size="sm"
                >
                  Matches
                </Button>
                <Button
                  render={<Link href={`/pipeline/${job.id}`} />}
                  variant="outline"
                  size="sm"
                >
                  Pipeline
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </Page>
  );
}
