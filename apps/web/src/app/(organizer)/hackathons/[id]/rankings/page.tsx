"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Trophy } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
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
  fetchHackathonRankings,
  finalizeHackathonRankings,
  pollRankingStatus,
  type RankingResponse,
} from "@/lib/api";

/** Composite weighting sent to the API. Previously the page *described* the split as
 * 0.40 judge / 0.30 pitch / 0.20 repo / 0.10 novelty while sending an even 0.25 each,
 * so organizers were told a formula the code did not use. One constant now feeds both
 * the request and the copy, so they cannot drift again. */
const WEIGHTS = {
  judge_weight: 0.25,
  pitch_weight: 0.25,
  repo_weight: 0.25,
  novelty_weight: 0.25,
} as const;

const WEIGHT_SUMMARY = "Equal weighting: judge, pitch, repo quality and novelty.";

export default function OrganizerRankingsPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const [finalizing, setFinalizing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchHackathonRankings(token, params.id);
  }, [getToken, params.id]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    `organizer:rankings:${params.id}`,
  );

  async function handleFinalize() {
    setFinalizing(true);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await finalizeHackathonRankings(token, params.id, { custom_weights: WEIGHTS });
      // Finalization runs in the background: the POST returns immediately and its
      // `rankings` are the previous run's, so poll for completion before re-fetching.
      const status = await pollRankingStatus(token, params.id);
      if (status.status === "failed") {
        const message = status.error ?? "Ranking finalization failed";
        setActionError(message);
        toast.error(message);
      } else if (status.status === "processing") {
        toast.info("Still finalizing", {
          description: "This is taking longer than usual - results will appear shortly.",
        });
      } else {
        toast.success("Rankings finalized", {
          description: "Top teams are now surfaced to recruiters.",
        });
      }
      if (status.status !== "failed") retry();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to finalize rankings";
      setActionError(message);
      toast.error(message);
    } finally {
      setFinalizing(false);
    }
  }

  const hasRankings = (data?.length ?? 0) > 0;

  return (
    <Page>
      <PageHeader
        title="Rankings"
        description={WEIGHT_SUMMARY}
        breadcrumb={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/events" />}>
                  My events
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Rankings</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        actions={
          <Button onClick={() => setConfirmOpen(true)} disabled={finalizing}>
            {finalizing ? "Finalizing…" : hasRankings ? "Re-finalize" : "Finalize rankings"}
          </Button>
        }
      />

      {actionError ? (
        <SectionError
          message={actionError}
          onRetry={() => setActionError(null)}
          retrying={false}
          className="mb-4"
        />
      ) : null}

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={5} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="No rankings yet"
          description="Once teams have submitted and judges have scored, finalize to compute standings."
          action={
            <Button size="sm" onClick={() => setConfirmOpen(true)} disabled={finalizing}>
              Finalize rankings
            </Button>
          }
        />
      ) : (
        <DataRowList>
          {data.map((ranking) => (
            <RankingRow key={ranking.id} ranking={ranking} />
          ))}
        </DataRowList>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        destructive={false}
        title={hasRankings ? "Re-finalize rankings?" : "Finalize rankings?"}
        description={
          hasRankings
            ? "Scores are recomputed and existing rankings are updated in place, not duplicated. Recruiters see the revised top teams."
            : "This computes final standings and surfaces the top teams to recruiters. You can re-finalize later if a judge score changes."
        }
        confirmLabel={hasRankings ? "Re-finalize" : "Finalize"}
        onConfirm={handleFinalize}
      />
    </Page>
  );
}

function RankingRow({ ranking }: { ranking: RankingResponse }) {
  const breakdown = ranking.score_breakdown;

  return (
    <DataRow
      title={
        <span className="flex items-center gap-2">
          <span data-numeric className="tabular-nums text-muted-foreground">
            #{ranking.rank}
          </span>
          {ranking.team_name ?? ranking.team_id}
        </span>
      }
      subtitle={
        breakdown
          ? `Judge ${fmt(breakdown.judge_score)} · Pitch ${fmt(breakdown.pitch_score)} · Repo ${fmt(breakdown.repo_quality_score)} · Novelty ${fmt(breakdown.novelty_score)}`
          : undefined
      }
      meta={
        <span data-numeric className="text-body font-medium tabular-nums">
          {ranking.composite_score.toFixed(1)}
          <span className="ml-1 text-meta font-normal text-muted-foreground">pts</span>
        </span>
      }
    />
  );
}

/** A missing sub-score means "not scored", which is not the same as zero. The label
 * says so rather than using an abbreviation that reads as an absent value. */
function fmt(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not scored" : value.toFixed(0);
}
