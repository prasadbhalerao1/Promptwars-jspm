"use client";

import Link from "next/link";
import { useCallback } from "react";
import { Trophy } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ListSkeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchMyHackathons } from "@/lib/api";

/** The organizer's event list.
 *
 * `GET /hackathons` (`list_my_hackathons`) is already organizer-gated and already
 * filtered to `organizer_user_id == user.id`, and `fetchMyHackathons` already existed
 * in the API client — but nothing called it and no page lived at this path. The
 * organizer sidebar's "My events" link therefore resolved to `(candidate)/hackathons`,
 * where the role gate bounced them straight back to /home. */
export default function OrganizerHackathonsPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchMyHackathons(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "organizer:hackathons",
  );

  return (
    <Page>
      <PageHeader
        title="My events"
        description="Hackathons you organize, from draft through to finalized rankings."
        actions={
          <Button size="sm" render={<Link href="/hackathons/new" />}>
            New hackathon
          </Button>
        }
      />

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={4} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="No events yet"
          description="Create a hackathon to import teams, assign scoring rubrics and publish rankings."
          action={
            <Button size="sm" render={<Link href="/hackathons/new" />}>
              Create your first hackathon
            </Button>
          }
        />
      ) : (
        <DataRowList>
          {data.map((event) => (
            <DataRow
              key={event.id}
              href={`/hackathons/${event.id}/manage`}
              title={event.name}
              subtitle={formatWindow(event.start_date, event.end_date)}
              meta={
                <>
                  {event.tracks?.length ? (
                    <span className="text-meta text-muted-foreground">
                      {event.tracks.length}{" "}
                      {event.tracks.length === 1 ? "track" : "tracks"}
                    </span>
                  ) : null}
                  <StatusBadge status={event.status} />
                </>
              }
            />
          ))}
        </DataRowList>
      )}
    </Page>
  );
}

function formatWindow(start: string | null, end: string | null): string {
  if (!start && !end) return "No dates set";
  const format = (value: string) => new Date(value).toLocaleDateString();
  if (start && end) return `${format(start)} - ${format(end)}`;
  return start ? `Starts ${format(start)}` : `Ends ${format(end as string)}`;
}
