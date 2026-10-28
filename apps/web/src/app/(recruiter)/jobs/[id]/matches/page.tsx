"use client";

import { Page, PageHeader } from "@/components/common/PageHeader";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  MatchBreakdown,
  MatchScore,
} from "@/components/common/MatchBreakdown";
import {
  fetchJobMatches,
  pollMatchingStatus,
  type MatchingStatusResponse,
} from "@/lib/api";

export default function RecruiterMatchesPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchJobMatches(token, params.id);
  }, [getToken, params.id]);
  const {
    data: matches,
    error,
    retry,
  } = useAsyncResource(fetcher, `job-matches:${params.id}`);

  // Without this the page showed a permanent "no candidates yet" message while matching
  // was still running in the background (or had failed outright). Poll the job's matching
  // status and re-fetch the match list once it finishes.
  const [matchingStatus, setMatchingStatus] =
    useState<MatchingStatusResponse | null>(null);
  // `retry` gets a new identity every render, so depending on it directly would restart
  // the poll loop constantly. Held in a ref instead — written in an effect rather than
  // during render, since a render-phase ref write is not safe under concurrent rendering
  // (React may render without committing, leaving the ref pointing at a discarded pass).
  const retryRef = useRef(retry);
  useEffect(() => {
    retryRef.current = retry;
  }, [retry]);

  useEffect(() => {
    // Was a hand-rolled `setTimeout(poll, 3000)` loop. It re-implemented the shared
    // helper minus the one property that matters: `pollUntil` sleeps via `pollDelay`,
    // which pauses while the tab is hidden. Without it a backgrounded matches tab kept
    // hitting the endpoint every 3s indefinitely.
    const controller = new AbortController();
    let wasProcessing = false;

    void (async () => {
      try {
        const token = await getToken();
        if (!token || controller.signal.aborted) return;
        const final = await pollMatchingStatus(token, params.id, {
          signal: controller.signal,
          // Render each intermediate status so the "matching in progress" state appears
          // immediately rather than only once polling settles.
          onUpdate: (status) => {
            if (controller.signal.aborted) return;
            setMatchingStatus(status);
            if (status.status === "processing") wasProcessing = true;
          },
        });
        // Matching just finished — pull the newly persisted rows in.
        if (!controller.signal.aborted && wasProcessing && final.status !== "processing") {
          retryRef.current();
        }
      } catch {
        // Status is supplementary: a failure here must not blank out the match list.
      }
    })();

    return () => controller.abort();
  }, [getToken, params.id]);

  const isProcessing = matchingStatus?.status === "processing";

  return (
    <Page>
      <PageHeader
        title="Matches"
        // "the full 4-term score breakdown" described the implementation. What a
        // recruiter needs to know is that no ranking is shown without its reasons.
        description="Candidates ranked against this role. Every score is shown with the evidence behind it, never as a bare percentage."
        actions={
          <Button
            render={<Link href={`/pipeline/${params.id}`} />}
            variant="outline"
          >
            View pipeline
          </Button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2 space-y-4">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Matched Candidates
            </CardTitle>
            {/* Was the raw formula and an internal doc reference. The four
                components are already listed per candidate below. */}
            <CardDescription>
              Ranked on skill overlap, semantic similarity, experience and
              talent-score alignment.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-destructive">{error}</p>}
            {!error && matches === null && <CardListSkeleton />}
            {matches !== null && matches.length === 0 && isProcessing && (
              <div className="space-y-3" aria-live="polite">
                <p className="text-sm text-muted-foreground">
                  Matching candidates against this role… this can take a moment.
                </p>
                <CardListSkeleton />
              </div>
            )}
            {matches !== null &&
              matches.length === 0 &&
              matchingStatus?.status === "failed" && (
                <p className="text-sm text-destructive">
                  Matching failed
                  {matchingStatus.error ? `: ${matchingStatus.error}` : "."} Try
                  recomputing from the job page.
                </p>
              )}
            {matches !== null &&
              matches.length === 0 &&
              !isProcessing &&
              matchingStatus?.status !== "failed" && (
                <p className="text-sm text-muted-foreground">
                  No candidates in the pool yet - matches will populate as
                  candidates onboard.
                </p>
              )}
            {matches?.map((match) => (
              <Card
                key={match.id}
                className="hover:border-primary transition-all"
              >
                <CardHeader className="flex flex-row justify-between items-start gap-4 pb-2">
                  <div>
                    <CardTitle className="text-base font-semibold">
                      {match.candidate_headline ??
                        match.candidate_github_username ??
                        "Candidate"}
                    </CardTitle>
                    {match.candidate_location && (
                      <Badge variant="outline" className="text-xs mt-2">
                        {match.candidate_location}
                      </Badge>
                    )}
                  </div>
                  <MatchScore value={match.match_percentage} />
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                  <p>{match.explanation}</p>
                  <MatchBreakdown
                    className="border-t border-border pt-3"
                    components={[
                      { label: "Skill overlap", value: match.skill_similarity },
                      {
                        label: "Semantic similarity",
                        value: match.semantic_similarity,
                      },
                      {
                        label: "Experience fit",
                        value: match.experience_match,
                      },
                      {
                        label: "Project relevance",
                        value: match.project_relevance,
                      },
                    ]}
                  />
                </CardContent>
              </Card>
            ))}
          </CardContent>
        </Card>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Ranking Rubric
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>
                Scores combine skill overlap (verified GitHub/badge signals
                weighted over self-declared resume text), embedding semantic
                similarity, experience fit, and the candidate&apos;s own Talent
                Score.
              </p>
              <p>
                Never shown as a bare percentage alone - the full breakdown is
                always visible.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
