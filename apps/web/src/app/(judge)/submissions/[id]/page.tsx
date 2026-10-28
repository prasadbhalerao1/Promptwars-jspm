"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Page, PageHeader } from "@/components/common/PageHeader";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { submitJudgeScore } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function JudgeRubricPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const hackathonId = searchParams.get("hackathonId");
  const teamName = searchParams.get("team");
  const { getToken } = useAuth();
  const [score, setScore] = useState("8");
  const [rationale, setRationale] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!hackathonId) {
      setError(
        "Missing hackathonId - open this page from the Evaluations Queue.",
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await submitJudgeScore(token, hackathonId, params.id, {
        score: Number(score),
        rationale: rationale || null,
      });
      setSubmitted(true);
      toast.success("Evaluation submitted");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to submit evaluation";
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page>
      <PageHeader
        // The team's name comes through the query string from the evaluation
        // queue; the previous title printed the raw submission UUID at the judge.
        title={teamName ?? "Score submission"}
        description="Give a score and the reasoning behind it."
        breadcrumb={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/evaluations" />}>
                  Evaluations
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Score</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Evaluation Rubric
            </CardTitle>
            <CardDescription>
              Rate execution, code quality, and project design parameters.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!submitted ? (
              <form onSubmit={handleSave} className="space-y-4">
                {/* This form asked for 0-100 while the evaluation queue renders
                    the same value as "n/10", so a judge entering 90 saw it come
                    back as "90/10". The backend takes a bare float with no bound,
                    so the UI is the only place the scale is defined, aligned to
                    the /10 the queue already displays. */}
                <div className="space-y-1">
                  <Label htmlFor="score">Score (0-10)</Label>
                  <Input
                    id="score"
                    type="number"
                    min="0"
                    max="10"
                    step="0.5"
                    required
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="rationale">Rationale</Label>
                  <Textarea
                    id="rationale"
                    required
                    className="min-h-24"
                    placeholder="Strengths, weaknesses, and how the project was executed…"
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" pending={submitting}>
                  {submitting ? "Submitting…" : "Submit Evaluation"}
                </Button>
              </form>
            ) : (
              <div className="p-4 bg-success/10 border border-success/20 rounded-md text-sm">
                <h4 className="font-semibold text-success">
                  Evaluation Submitted
                </h4>
                <p className="text-xs text-muted-foreground mt-1">
                  Rubric grading successfully logged. Standing computations will
                  run when the organizer finalizes rankings.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Rubric Criteria
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>
                Ratings are evaluated on:
                <br />• <strong>Code Quality</strong>: Design patterns &
                coverage.
                <br />• <strong>Feasibility</strong>: Practical operation.
                <br />• <strong>Innovation</strong>: Uniqueness of concept.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
