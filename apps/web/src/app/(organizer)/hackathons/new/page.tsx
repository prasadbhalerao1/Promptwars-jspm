"use client";

import { Page, PageHeader } from "@/components/common/PageHeader";

import { toast } from "sonner";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { createHackathon } from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function OrganizerNewHackathonPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [track, setTrack] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const hackathon = await createHackathon(token, {
        name,
        tracks: track ? [track] : [],
        ingestion_mode: "direct",
      });
      router.push(`/hackathons/${hackathon.id}/manage`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create hackathon";
      setError(message);
      toast.error(message);
      setSubmitting(false);
    }
  }

  return (
    <Page>
      <PageHeader
        title="New event"
        description="Register a hiring hackathon and define its evaluation tracks."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Hackathon Details
            </CardTitle>
            <CardDescription>
              Configure hackathon names, durations, and criteria.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="name">Hackathon Name</Label>
                <Input
                  id="name"
                  required
                  placeholder="e.g. Winter Developer Challenge 2026"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="track">Evaluation Track</Label>
                <Input
                  id="track"
                  placeholder="e.g. Full-Stack Dev, ML Algorithms"
                  value={track}
                  onChange={(e) => setTrack(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" pending={submitting}>
                {submitting ? "Creating…" : "Create Event"}
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
                Hackathon events integrate directly into matches. Finalizing
                rankings triggers:
                <br />• The `hackathon.rankings.finalized` event, naming the top
                3 teams.
                <br />• Recruiter watchlist visibility via the Top Performers
                feed.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
