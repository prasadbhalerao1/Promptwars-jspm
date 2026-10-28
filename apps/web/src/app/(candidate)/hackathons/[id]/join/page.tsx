"use client";

import { toast } from "sonner";
import { useAuth } from "@/components/AuthProvider";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import {
  fetchHackathon,
  submitHackathonProject,
  type TeamMemberInput,
} from "@/lib/api";
import { Input } from "@/components/ui/input";

// QA finding (Track 2): no page called `submitHackathonProject()` (POST
// /hackathons/{id}/submissions), so candidates couldn't join a hackathon through the
// UI even though the backend endpoint already worked. Form fields below mirror
// `TeamSubmissionInput` exactly (packages/shared_schemas/hackathon.py) — team_name is
// the only required field; track/repo_url/presentation_id/members are all optional.
// `judge_score` is intentionally omitted — it's an organizer/judge-only field this form
// must never set.
export default function CandidateHackathonJoinPage() {
  const params = useParams<{ id: string }>();
  const hackathonId = params.id;
  const router = useRouter();
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchHackathon(token, hackathonId);
  }, [getToken, hackathonId]);

  const {
    data: hackathon,
    error: loadError,
    loading,
    retry,
  } = useAsyncResource(fetcher, `candidate:hackathon:${hackathonId}`);

  const [teamName, setTeamName] = useState("");
  const [track, setTrack] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [presentationId, setPresentationId] = useState("");
  const [memberGithubUsername, setMemberGithubUsername] = useState("");
  const [memberDisplayName, setMemberDisplayName] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!teamName.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");

      const members: TeamMemberInput[] = [];
      if (memberGithubUsername.trim() || memberDisplayName.trim()) {
        members.push({
          github_username: memberGithubUsername.trim() || null,
          display_name: memberDisplayName.trim() || null,
          role: "member",
        });
      }

      await submitHackathonProject(token, hackathonId, {
        team_name: teamName.trim(),
        track: track.trim() || null,
        members,
        repo_url: repoUrl.trim() || null,
        presentation_id: presentationId.trim() || null,
      });
      setSuccess(true);
      toast.success("Project submitted");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit project";
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page width="reading">
      <PageHeader
        title={hackathon ? `Submit to ${hackathon.name}` : "Submit project"}
        description="Register your team and link your repo and pitch deck. Re-submitting with the same team name updates your entry."
      />

      {/* The event's name is a nicety here, not a prerequisite — the form posts to
          the id from the URL either way, so a failed load degrades to a generic
          title rather than blocking submission. */}
      {loadError ? (
        <SectionError
          message={loadError}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Team Submission
          </CardTitle>
          <CardDescription>
            Only the team name is required - add what you have, update it later
            if needed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {success ? (
            <div className="space-y-4">
              <p className="text-sm text-success">
                Submission received! Your team is now in the running.
              </p>
              <Button
                variant="outline"
                onClick={() => router.push("/hackathons")}
              >
                Back to Hackathons
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="team_name">Team Name</Label>
                <Input
                  id="team_name"
                  required
                  placeholder="e.g. Byte Me"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="track">Track</Label>
                <Input
                  id="track"
                  placeholder="e.g. Full-Stack Dev"
                  value={track}
                  onChange={(e) => setTrack(e.target.value)}
                />
                {hackathon?.tracks && hackathon.tracks.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Available tracks: {hackathon.tracks.join(", ")}
                  </p>
                )}
              </div>

              <div className="space-y-1">
                <Label htmlFor="repo_url">Repository URL</Label>
                <Input
                  id="repo_url"
                  type="url"
                  placeholder="https://github.com/your-team/project"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="presentation_id">Pitch Deck ID</Label>
                <Input
                  id="presentation_id"
                  placeholder="From the Pitch Deck Analyzer's upload confirmation"
                  value={presentationId}
                  onChange={(e) => setPresentationId(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Upload your deck under Pitch Deck Analyzer first, then paste
                  the presentation ID it returns.
                </p>
              </div>

              {/* Unprefixed grid-cols-2: at 375px these two labelled inputs were
                  ~150px each and the labels wrapped to three lines. */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="member_github">
                    Teammate GitHub Username
                  </Label>
                  <Input
                    id="member_github"
                    placeholder="optional"
                    value={memberGithubUsername}
                    onChange={(e) => setMemberGithubUsername(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="member_name">Teammate Display Name</Label>
                  <Input
                    id="member_name"
                    placeholder="optional"
                    value={memberDisplayName}
                    onChange={(e) => setMemberDisplayName(e.target.value)}
                  />
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button
                type="submit"
                className="w-full"
                pending={submitting}
                disabled={!teamName.trim()}
              >
                {submitting ? "Submitting…" : "Submit Project"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </Page>
  );
}
