"use client";

import { useParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { useCallback, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { ListSkeleton } from "@/components/common/Skeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  fetchHackathon,
  fetchHackathonTeams,
  importHackathonTeamsCsv,
} from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function OrganizerManageHackathonPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);

  const [teamName, setTeamName] = useState("");
  const [track, setTrack] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [judgeScore, setJudgeScore] = useState("");
  const [members, setMembers] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // useAsyncResource owns the mount fetch, cancellation and transient-failure retry.
  // `retry()` replaces the manual `load()` re-read that mutations called.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    const [hackathon, teams] = await Promise.all([
      fetchHackathon(token, params.id),
      fetchHackathonTeams(token, params.id),
    ]);
    return { hackathon, teams };
  }, [getToken, params.id]);

  const {
    data,
    error: loadError,
    loading,
    retry,
  } = useAsyncResource(fetcher, `organizer:manage:${params.id}`);

  const hackathon = data?.hackathon ?? null;
  const teams = data?.teams ?? [];
  const error = actionError ?? loadError;

  async function handleAddTeam(e: React.FormEvent) {
    e.preventDefault();
    if (!teamName) return;
    setSubmitting(true);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await importHackathonTeamsCsv(token, params.id, [
        {
          team_name: teamName,
          track: track || null,
          repo_url: repoUrl || null,
          judge_score: judgeScore ? Number(judgeScore) : null,
          members: members
            .split(",")
            .map((m) => m.trim())
            .filter(Boolean)
            .map((github_username) => ({ github_username })),
        },
      ]);
      setTeamName("");
      setTrack("");
      setRepoUrl("");
      setJudgeScore("");
      setMembers("");
      toast.success(`Added ${teamName}`);
      retry();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add team";
      setActionError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page>
      <PageHeader
        // The event's name is the title; "Manage Hackathon Event" described the page,
        // and the subtitle cited an internal requirement id (FR-7a) at the organizer.
        title={hackathon?.name ?? "Manage event"}
        description="Register teams and their repositories. Judges score from the evaluation queue."
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
                <BreadcrumbPage>Manage</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            render={<Link href={`/hackathons/${params.id}/rankings`} />}
          >
            Rankings
          </Button>
        }
      />

      {loading && !hackathon ? <ListSkeleton rows={3} /> : null}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2 space-y-4">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Registered Teams
            </CardTitle>
            <CardDescription>
              {teams.length} team(s) registered so far.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {teams.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No teams yet - add one below.
              </p>
            )}
            {teams.map((t) => (
              <div
                key={t.id}
                className="p-3 border rounded-md bg-card flex justify-between items-center"
              >
                <div>
                  <p className="font-medium text-foreground">{t.team_name}</p>
                  {t.track && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Track: {t.track}
                    </p>
                  )}
                </div>
                <Badge>Registered</Badge>
              </div>
            ))}

            <form
              onSubmit={handleAddTeam}
              className="space-y-3 pt-4 border-t mt-4"
            >
              <h4 className="font-semibold text-sm text-foreground">
                Add a Team
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="teamName">Team Name</Label>
                  <Input
                    id="teamName"
                    required
                    value={teamName}
                    onChange={(e) => setTeamName(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="teamTrack">Track</Label>
                  <Input
                    id="teamTrack"
                    value={track}
                    onChange={(e) => setTrack(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="repoUrl">Repo URL (optional)</Label>
                <Input
                  id="repoUrl"
                  placeholder="https://github.com/org/repo"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="judgeScore">Judge Score (optional)</Label>
                  <Input
                    id="judgeScore"
                    type="number"
                    min={0}
                    max={100}
                    value={judgeScore}
                    onChange={(e) => setJudgeScore(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="members">
                    Member GitHub usernames (comma separated)
                  </Label>
                  <Input
                    id="members"
                    placeholder="octocat, defunkt"
                    value={members}
                    onChange={(e) => setMembers(e.target.value)}
                  />
                </div>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" pending={submitting}>
                {submitting ? "Adding…" : "Add Team"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Event Parameters
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>
                Manual roster entry reuses the same CSV-import path organizers
                would use for a bulk file (FR-7a) - one row at a time here, same
                backend endpoint.
              </p>
              <p>
                Teams can also self-register their own repo/deck link directly
                (FR-7c) once candidates log in.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
