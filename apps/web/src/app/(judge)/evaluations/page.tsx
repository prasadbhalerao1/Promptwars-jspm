"use client";

import { useCallback, useMemo } from "react";
import { Gavel } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader, SectionHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchJudgingQueue, type JudgeQueueEntry } from "@/lib/api";

/** The judge's queue — and, since `/evaluations` is their only route, effectively the
 * whole product for this role.
 *
 * Unscored submissions lead: a judge opens this page to find work, not to browse a
 * mixed list. Previously everything was one undifferentiated list ordered by the API. */
export default function JudgeEvaluationsQueuePage() {
  const { getToken } = useAuth();

  // Was a hand-rolled useEffect + three useState hooks, which meant this page got none
  // of useAsyncResource's 429/backoff handling. It also returned early when no token
  // resolved *without* clearing `loading`, so that path spun a skeleton forever.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchJudgingQueue(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(fetcher, "judge:queue");

  const { pending, scored } = useMemo(() => {
    const entries = data ?? [];
    return {
      pending: entries.filter((entry) => entry.judge_score === null),
      scored: entries.filter((entry) => entry.judge_score !== null),
    };
  }, [data]);

  return (
    <Page>
      <PageHeader
        title="Evaluation queue"
        description="Score submitted projects against the rubric. Your ratings combine with automated code and deck analysis in the final ranking."
      />

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={5} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={Gavel}
          title="Nothing to evaluate yet"
          description="Submissions appear here once teams have submitted their projects to a hackathon you're judging."
        />
      ) : (
        <div className="space-y-8">
          <section>
            <SectionHeader
              title="Awaiting your score"
              description={
                pending.length === 0
                  ? "You've scored everything in the queue."
                  : `${pending.length} of ${data.length} submissions`
              }
            />
            {pending.length === 0 ? (
              <EmptyState
                icon={Gavel}
                title="All caught up"
                description="Every submission in your queue has been scored."
              />
            ) : (
              <DataRowList>
                {pending.map((submission) => (
                  <SubmissionRow key={submission.submission_id} submission={submission} />
                ))}
              </DataRowList>
            )}
          </section>

          {scored.length > 0 ? (
            <section>
              <SectionHeader
                title="Already scored"
                description="Open one to revise your rating."
              />
              <DataRowList>
                {scored.map((submission) => (
                  <SubmissionRow key={submission.submission_id} submission={submission} />
                ))}
              </DataRowList>
            </section>
          ) : null}
        </div>
      )}
    </Page>
  );
}

function SubmissionRow({ submission }: { submission: JudgeQueueEntry }) {
  const isScored = submission.judge_score !== null;

  return (
    <DataRow
      // The whole row is the target. It previously ended in a small "Evaluate →" text
      // link, which is a needlessly precise thing to ask someone to hit repeatedly.
      // `team` rides along so the scoring page can title itself with the team's
      // name instead of printing the raw submission UUID at the judge. It has no
      // endpoint of its own to resolve a submission to a team.
      href={`/submissions/${submission.submission_id}?hackathonId=${submission.hackathon_id}&team=${encodeURIComponent(submission.team_name)}`}
      title={submission.team_name}
      subtitle={submission.hackathon_name}
      meta={
        isScored ? (
          <Badge variant="outline" className="font-normal">
            <span data-numeric className="tabular-nums">
              {submission.judge_score}
            </span>
            <span className="text-muted-foreground">/10</span>
          </Badge>
        ) : (
          <StatusBadge status="pending" label="Not scored" />
        )
      }
    />
  );
}
