"use client";

import { useCallback } from "react";
import Link from "next/link";
import { Trophy } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { fetchOpenHackathons } from "@/lib/api";

// Candidates reach hackathons through `GET /hackathons/open`; the plain
// `GET /hackathons` is organizer-scoped and 403s a candidate token.
export default function CandidateHackathonsPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchOpenHackathons(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "candidate:open-hackathons",
  );
  const hackathons = data ?? [];

  return (
    <Page>
      <PageHeader
        title="Hackathons"
        description="Join an open event and submit your team's project. Recruiters watch top-ranked teams."
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

      {data && hackathons.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="No open hackathons"
          description="Nothing is accepting submissions right now. New events appear here as organizers open them."
        />
      ) : null}

      {hackathons.length > 0 && (
        <ul className="space-y-3">
          {hackathons.map((hackathon) => (
            <li
              key={hackathon.id}
              className="flex flex-wrap items-start justify-between gap-4 rounded-xl px-4 py-4 shadow-flat"
            >
              <div className="min-w-0 space-y-2">
                <div>
                  <h2 className="text-body font-medium text-foreground">
                    {hackathon.name}
                  </h2>
                  <p className="mt-0.5 text-meta text-muted-foreground">
                    {hackathon.start_date && hackathon.end_date
                      ? `${new Date(hackathon.start_date).toLocaleDateString()} - ${new Date(hackathon.end_date).toLocaleDateString()}`
                      : "Dates to be announced"}
                  </p>
                </div>
                {hackathon.tracks && hackathon.tracks.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {hackathon.tracks.map((track) => (
                      <Badge key={track} variant="outline">
                        {track}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <Button
                size="sm"
                render={<Link href={`/hackathons/${hackathon.id}/join`} />}
              >
                Submit project
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
