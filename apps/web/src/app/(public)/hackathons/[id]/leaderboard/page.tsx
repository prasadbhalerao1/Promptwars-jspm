"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { Trophy } from "lucide-react";

import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  fetchPublicHackathon,
  fetchPublicHackathonRankings,
} from "@/lib/api";

/** Public standings. No sign-in required — this is the page an event shares publicly,
 * so it names the event rather than describing itself as "Public Leaderboard". */
export default function PublicLeaderboardPage() {
  const params = useParams<{ id: string }>();

  const fetcher = useCallback(async () => {
    const [hackathon, rankings] = await Promise.all([
      fetchPublicHackathon(params.id),
      fetchPublicHackathonRankings(params.id),
    ]);
    return { hackathon, rankings };
  }, [params.id]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    `public:leaderboard:${params.id}`,
  );

  return (
    <Page>
      <PageHeader
        title={data?.hackathon.name ?? "Leaderboard"}
        description="Final standings, combining judge ratings with automated code and deck analysis."
      />

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={6} />
      ) : data.rankings.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="Rankings not finalized yet"
          description="Standings appear here once the organizer finalizes results for this event."
        />
      ) : (
        <DataRowList>
          {data.rankings.map((ranking) => (
            <DataRow
              key={ranking.id}
              href={`/hackathons/${params.id}/teams/${ranking.team_id}`}
              title={
                <span className="flex items-center gap-2">
                  <span data-numeric className="tabular-nums text-muted-foreground">
                    #{ranking.rank}
                  </span>
                  {ranking.team_name ?? ranking.team_id}
                </span>
              }
              meta={
                <span data-numeric className="text-body font-medium tabular-nums">
                  {ranking.composite_score.toFixed(1)}
                  <span className="ml-1 text-meta font-normal text-muted-foreground">
                    pts
                  </span>
                </span>
              }
            />
          ))}
        </DataRowList>
      )}
    </Page>
  );
}
