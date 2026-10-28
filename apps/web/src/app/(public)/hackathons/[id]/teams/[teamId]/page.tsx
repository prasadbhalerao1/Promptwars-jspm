"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchPublicHackathonTeamDetail } from "@/lib/api";

export default function PublicTeamPage() {
  const params = useParams<{ id: string; teamId: string }>();

  const fetcher = useCallback(
    () => fetchPublicHackathonTeamDetail(params.id, params.teamId),
    [params.id, params.teamId],
  );

  const {
    data: detail,
    error,
    loading,
    retry,
  } = useAsyncResource(fetcher, `public:team:${params.teamId}`);

  return (
    <Page>
      <PageHeader
        title={detail?.team.team_name ?? "Team"}
        // The subtitle used to print the raw hackathon UUID, which tells a public
        // visitor nothing. A link back to the leaderboard is the useful thing here.
        breadcrumb={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink
                  render={<Link href={`/hackathons/${params.id}/leaderboard`} />}
                >
                  Leaderboard
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Team</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
      />

      {loading && !detail ? <ListSkeleton rows={3} /> : null}
      {error && !detail ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : null}

      {detail && (
        <div className="max-w-reading">
          <Card>
            <CardHeader>
              <CardTitle>Submission</CardTitle>
              <CardDescription>
                Participants, repository and final standing.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <div className="flex justify-between border-b pb-2">
                <span className="font-semibold text-foreground">
                  GitHub Repository
                </span>
                {detail.submission?.repo_url ? (
                  <a
                    href={detail.submission.repo_url}
                    className="text-primary hover:underline"
                  >
                    {detail.submission.repo_url}
                  </a>
                ) : (
                  <span>Not linked</span>
                )}
              </div>
              {detail.ranking && (
                <div className="flex justify-between border-b pb-2">
                  <span className="font-semibold text-foreground">
                    Composite Score
                  </span>
                  <span>
                    #{detail.ranking.rank} -{" "}
                    {detail.ranking.composite_score.toFixed(1)} pts
                  </span>
                </div>
              )}
              <div className="space-y-2">
                <h4 className="font-semibold text-foreground">Team Members</h4>
                <ul className="list-disc list-inside text-xs space-y-1">
                  {detail.members.map((m) => (
                    <li key={m.id}>
                      {m.display_name ??
                        m.github_username ??
                        "Unregistered member"}{" "}
                      ({m.role})
                    </li>
                  ))}
                  {detail.members.length === 0 && (
                    <li>No members registered</li>
                  )}
                </ul>
              </div>
            </CardContent>
          </Card>
          {/* A "Public Page Info" card here explained that the page is public. A
              visitor reading it is already looking at it. */}
        </div>
      )}
    </Page>
  );
}
