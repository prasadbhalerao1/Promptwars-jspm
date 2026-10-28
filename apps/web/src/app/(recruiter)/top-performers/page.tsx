"use client";

import { useCallback } from "react";
import { Trophy } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { Badge } from "@/components/ui/badge";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchTopPerformersFeed, type TopPerformerEntry } from "@/lib/api";

/** Standouts surfaced from finalized hackathon rankings.
 *
 * Watchlist matches sort first (the API already does this), and the feed always
 * includes recent top-3 finishers so it is never empty for a recruiter with no
 * watchlist configured. */
export default function RecruiterTopPerformersPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchTopPerformersFeed(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(fetcher, "recruiter:top");
  const entries = data?.entries ?? null;

  return (
    <Page>
      <PageHeader
        title="Top performers"
        description="Top-three finishers from finalized hackathons. Candidates matching your watchlist are highlighted and listed first."
      />

      {error && !entries ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !entries ? (
        <ListSkeleton rows={5} />
      ) : entries.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="No ranked performers yet"
          description="Candidates appear here once a hackathon organizer finalizes their event rankings."
        />
      ) : (
        <DataRowList>
          {entries.map((entry, index) => (
            <PerformerRow
              key={`${entry.team_id}-${entry.candidate_id ?? index}`}
              entry={entry}
            />
          ))}
        </DataRowList>
      )}
    </Page>
  );
}

function PerformerRow({ entry }: { entry: TopPerformerEntry }) {
  const name = entry.candidate_github_username ?? entry.team_name;

  return (
    <DataRow
      title={
        <span className="flex items-center gap-2">
          <span data-numeric className="tabular-nums text-muted-foreground">
            #{entry.rank}
          </span>
          {name}
        </span>
      }
      subtitle={
        entry.candidate_headline
          ? `${entry.hackathon_name} · ${entry.candidate_headline}`
          : `${entry.hackathon_name} · team ${entry.team_name}`
      }
      meta={
        <>
          {entry.matched_watchlist ? (
            <Badge
              variant="outline"
              className="font-normal text-primary"
              // The reasons are the useful part of a match, so they ride along as a
              // tooltip rather than pushing the row to a third line.
              title={
                entry.match_reasons.length > 0
                  ? `Matched on: ${entry.match_reasons.join(", ")}`
                  : undefined
              }
            >
              Watchlist match
            </Badge>
          ) : null}
          <Badge variant="outline" className="font-normal">
            <span data-numeric className="tabular-nums">
              {entry.composite_score.toFixed(1)}
            </span>
          </Badge>
        </>
      }
    />
  );
}
