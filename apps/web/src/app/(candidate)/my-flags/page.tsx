"use client";

import { Page, PageHeader } from "@/components/common/PageHeader";

// Doc/SRS/06 §9's `(candidate)/my-flags/page.tsx` — "view flags against self, submit
// dispute." Wired to the real Module 06 backend (see .agents/decisions.md's Module 06
// entry): `raised`/`under_review` flags are shown as pending review, NEVER as a guilt
// verdict — the authenticity score card frames the same idea positively ("corroboration
// strength," doc 06 §5), matching the stub's own "Flags do not auto-reject candidates"
// copy, which is now backed by a real backend guarantee rather than mock text.

import { useCallback, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AuthenticityScoreResponse,
  fetchAuthenticityScore,
  fetchCandidateFlags,
  fetchDashboard,
  FraudFlagResponse,
  submitFlagDispute,
} from "@/lib/api";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ShieldCheck } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

const STATUS_LABEL: Record<string, string> = {
  raised: "Pending Review",
  under_review: "Under Review (dispute submitted)",
  upheld: "Upheld",
  dismissed: "Dismissed",
};

export default function CandidateFlagsPage() {
  const { getToken } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [disputeText, setDisputeText] = useState<Record<string, string>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [submittedIds, setSubmittedIds] = useState<Set<string>>(new Set());

  // Migrated off a hand-rolled useEffect so this page gets the same 429/backoff
  // retrying as the rest of the app.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    const dashboard = await fetchDashboard(token);
    const id = dashboard.profile.id;
    const [flags, score] = await Promise.all([
      fetchCandidateFlags(token, id),
      fetchAuthenticityScore(token, id),
    ]);
    return { candidateId: id, flags, score };
  }, [getToken]);

  const { data, error: loadError, loading, retry } = useAsyncResource(
    fetcher,
    "candidate:flags",
  );

  const flags: FraudFlagResponse[] = data?.flags ?? [];
  const score: AuthenticityScoreResponse | null = data?.score ?? null;
  const error = actionError ?? loadError;

  async function handleSubmitDispute(flagId: string) {
    const statement = (disputeText[flagId] ?? "").trim();
    if (!statement) return;
    setSubmittingId(flagId);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await submitFlagDispute(token, flagId, {
        candidate_statement: statement,
      });
      setSubmittedIds((prev) => new Set(prev).add(flagId));
      toast.success("Dispute submitted", {
        description: "A reviewer will look at your statement alongside the evidence.",
      });
      // Re-reads flags and score together so the dispute's new status is reflected.
      retry();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit dispute";
      setActionError(message);
      toast.error(message);
    } finally {
      setSubmittingId(null);
    }
  }

  return (
    <Page>
      <PageHeader
        title="Trust flags"
        description="Integrity flags raised on your profile. Nothing counts against you until a human reviewer upholds it - you can dispute any of them."
      />

      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && <CardListSkeleton />}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Active Profile Flags
            </CardTitle>
            <CardDescription>
              Integrity issues flagged by the platform&apos;s multi-agent
              checking system.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!loading && flags.length === 0 && (
              <EmptyState
                icon={ShieldCheck}
                title="Nothing flagged"
                description="No authenticity checks have raised anything on your profile. If one ever does, it appears here with the evidence and a way to dispute it."
              />
            )}

            {flags.map((flag) => {
              const canDispute = flag.status === "raised";
              const alreadySubmitted = submittedIds.has(flag.id);
              const reportSummary =
                typeof flag.evidence?.report_summary === "string"
                  ? (flag.evidence.report_summary as string)
                  : null;
              return (
                <div
                  key={flag.id}
                  className="p-4 bg-destructive/10 border border-destructive/20 rounded-md space-y-3"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="text-sm font-semibold text-destructive capitalize">
                        {flag.flag_type.replace(/_/g, " ")}
                      </h4>
                      <p className="text-xs text-muted-foreground mt-1">
                        {reportSummary ?? "See evidence details."}
                      </p>
                      <span className="inline-block mt-2 px-2 py-0.5 text-meta font-medium bg-destructive text-destructive-foreground rounded-sm">
                        Flagged: {new Date(flag.raised_at).toLocaleDateString()}
                      </span>
                    </div>
                    <Badge variant="outline" className="capitalize">
                      {STATUS_LABEL[flag.status] ?? flag.status}
                    </Badge>
                  </div>

                  {canDispute && !alreadySubmitted && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleSubmitDispute(flag.id);
                      }}
                      className="space-y-2 pt-3 border-t"
                    >
                      <label className="text-xs font-medium text-muted-foreground">
                        Explain the circumstances of this flag:
                      </label>
                      <Textarea
                        required
                        placeholder="Provide details for review (e.g., shared starter template, coincidental overlap, etc.)"
                        value={disputeText[flag.id] ?? ""}
                        onChange={(e) =>
                          setDisputeText((prev) => ({
                            ...prev,
                            [flag.id]: e.target.value,
                          }))
                        }
                      />
                      <Button type="submit" disabled={submittingId === flag.id}>
                        {submittingId === flag.id
                          ? "Submitting…"
                          : "Submit Dispute"}
                      </Button>
                    </form>
                  )}

                  {(alreadySubmitted || flag.status === "under_review") && (
                    <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm">
                      <p className="text-xs text-muted-foreground">
                        Your dispute has been submitted. Admin review has been
                        scheduled - you will be notified of the decision within
                        48 hours.
                      </p>
                    </div>
                  )}

                  {flag.status === "upheld" && (
                    <div className="p-3 bg-warning/10 border border-warning/20 rounded-md text-sm">
                      <p className="text-xs text-muted-foreground">
                        This flag was upheld after human review. Reviewer notes:{" "}
                        {flag.review_notes ?? "(none provided)"}
                      </p>
                    </div>
                  )}

                  {flag.status === "dismissed" && (
                    <div className="p-3 bg-success/10 border border-success/20 rounded-md text-sm">
                      <p className="text-xs text-muted-foreground">
                        This flag was reviewed and dismissed - no action was
                        taken.
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Authenticity Score
              </CardTitle>
              <CardDescription>
                Corroboration strength - not a guilt score.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {score ? (
                <div className="text-center">
                  <div className="text-4xl font-bold text-foreground">
                    {score.score.toFixed(0)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    out of 100
                  </p>
                  {score.components &&
                    score.components.penalties_applied.length > 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        {score.components.penalties_applied.length} upheld
                        issue(s) on record.
                      </p>
                    )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Not yet computed.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Integrity Policy
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>
                **Proof over Paperwork**: TRACE maintains strict checks on code
                plagiarism, certificate authenticity, and duplicate profiles.
              </p>
              <p>
                Flags do **not** auto-reject candidates; only a flag a human
                reviewer upholds - with written notes - can ever affect anything
                downstream.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
