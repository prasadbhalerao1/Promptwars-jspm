"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { GitCommitHorizontal } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { ListSkeleton } from "@/components/common/Skeleton";
import { ContributionBarChart } from "@/components/ContributionBarChart";
import { fetchContributionReports } from "@/lib/api";

export default function RecruiterContributionReportPage() {
  const params = useParams<{ repo: string }>();
  const repoFullName = decodeURIComponent(params.repo);
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchContributionReports(token, repoFullName);
  }, [getToken, repoFullName]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    `recruiter:contribution:${repoFullName}`,
  );
  const reports = data ?? [];

  return (
    <Page>
      <PageHeader
        // The repo is what the reader is looking at, so it is the title rather
        // than being buried in a card header below a generic page name.
        title={repoFullName}
        description="Commit attribution and weighted contribution share per team member."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !data ? <ListSkeleton rows={4} /> : null}

      {data && reports.length === 0 ? (
        <EmptyState
          icon={GitCommitHorizontal}
          title="No contribution report yet"
          description="Nothing has been generated for this repository. Reports are produced once the repo has been analysed."
        />
      ) : null}

      {reports.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <Card className="space-y-4 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Contribution share
              </CardTitle>
              <CardDescription>
                Weighted from surviving lines, commits, pull requests opened and
                reviews - not raw commit count.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ContributionBarChart reports={reports} />
              <ul>
                {reports.map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-start justify-between gap-2 border-b border-border py-3 last:border-0"
                  >
                    <div>
                      <p className="text-body font-medium text-foreground">
                        {r.github_username}
                      </p>
                      {r.anomaly_note && (
                        <p className="mt-0.5 text-meta text-warning">
                          {r.anomaly_note}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p
                        data-numeric
                        className="text-body font-medium tabular-nums text-foreground"
                      >
                        {((r.contribution_share ?? 0) * 100).toFixed(0)}%
                      </p>
                      <p className="text-meta tabular-nums text-muted-foreground">
                        {r.commits} commits · {r.prs_opened} PRs ·{" "}
                        {r.prs_reviewed} reviews
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <div>
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold">
                  Reading this report
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-meta leading-relaxed text-muted-foreground">
                <p>
                  An anomaly means no contribution could be attributed despite
                  team membership. It is a note for human review, never an
                  automatic penalty.
                </p>
                <p>
                  {/* The raw formula was previously printed at the recruiter as a
                      card description. The components are shown per person above,
                      which is the part that is actually actionable. */}
                  Raw components are shown alongside each share, so the number
                  can be checked rather than taken on trust.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
