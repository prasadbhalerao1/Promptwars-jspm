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
import { Badge } from "@/components/ui/badge";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { APPLICATION_STAGE_LABELS, fetchMyApplications } from "@/lib/api";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function CandidateApplicationsPage() {
  const { getToken } = useAuth();
  const applicationsFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchMyApplications(token);
  }, [getToken]);
  const { data: applications, error } = useAsyncResource(
    applicationsFetcher,
    "applications:mine",
  );

  return (
    <Page>
      <PageHeader
        title="Applications"
        description="Where each of your applications stands in the recruiter's pipeline."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Active Applications
            </CardTitle>
            <CardDescription>
              Track interview stages as recruiters move you through their
              pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-destructive">{error}</p>}
            {!error && applications === null && <CardListSkeleton />}
            {applications !== null && applications.length === 0 && (
              <EmptyState
                icon={ListChecks}
                title="No applications yet"
                description="Every role you apply to is tracked here, with the stage it has reached."
                action={
                  <Button render={<Link href="/jobs" />}>Browse jobs</Button>
                }
              />
            )}
            {applications?.map((app) => (
              <div
                key={app.id}
                className="p-4 border rounded-md hover:border-primary transition-all flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card shadow-flat"
              >
                <div>
                  <h4 className="text-sm font-semibold text-foreground">
                    {app.job_title}
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {app.job_location ?? "Remote"} • Applied on{" "}
                    {new Date(app.applied_at).toLocaleDateString()}
                  </p>
                </div>
                <Badge
                  variant={app.stage === "hired" ? "secondary" : "outline"}
                  className="capitalize"
                >
                  {APPLICATION_STAGE_LABELS[app.stage]}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Pipeline Stages
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>
                Sourced → Screened → Interview Scheduled → Offered →
                Hired/Rejected.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
