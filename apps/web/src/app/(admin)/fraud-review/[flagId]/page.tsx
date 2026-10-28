"use client";

// Doc/SRS/06 §9's `(admin)/fraud-review/[flagId]/page.tsx`. Wired to the real Module 06
// backend: `GET /flags/{id}` (evidence + candidate's dispute + Dispute Review Agent's
// assistive summary — which NEVER recommends a verdict, see
// `services/agents/fraud/tools/dispute_review_llm.py`) and
// `PATCH /flags/{id}/review` (the only place a flag can move to upheld/dismissed).
// `review_notes` is required client-side before an Uphold submit is even attempted,
// mirroring the backend's hard 422 rejection of an empty-notes uphold
// (`.agents/decisions.md`'s Module 06 entry) — this is a UX nicety on top of a real
// server-side guarantee, not a substitute for it.

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import Link from "next/link";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  fetchFraudFlagDetail,
  reviewFraudFlag,
} from "@/lib/api";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { Textarea } from "@/components/ui/textarea";

export default function AdminFlagAuditPage() {
  const params = useParams<{ flagId: string }>();
  const { getToken } = useAuth();

  const [actionError, setActionError] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [submitting, setSubmitting] = useState<"upheld" | "dismissed" | null>(
    null,
  );
  const [resolution, setResolution] = useState<string | null>(null);

  // Migrated off a hand-rolled useEffect + load() pair; the dependency array had to be
  // eslint-disabled because load() was redefined every render. useAsyncResource owns
  // the fetch, the retry and the cancellation, and `retry()` replaces the manual
  // re-read after a review decision.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchFraudFlagDetail(token, params.flagId);
  }, [getToken, params.flagId]);

  const {
    data: detail,
    error: loadError,
    loading,
    retry,
  } = useAsyncResource(fetcher, `admin:flag:${params.flagId}`);

  const error = actionError ?? loadError;

  async function handleAction(status: "upheld" | "dismissed") {
    if (status === "upheld" && !reviewNotes.trim()) {
      setActionError("Review notes are required to uphold a flag.");
      return;
    }
    setSubmitting(status);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await reviewFraudFlag(token, params.flagId, {
        status,
        review_notes: reviewNotes || null,
      });
      setResolution(status);
      toast.success(status === "upheld" ? "Flag upheld" : "Flag dismissed", {
        description:
          status === "upheld"
            ? "This now counts toward the candidate's authenticity score."
            : "No effect on the candidate's profile.",
      });
      retry();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to submit review";
      setActionError(message);
      toast.error(message);
    } finally {
      setSubmitting(null);
    }
  }

  const evidenceItems = Array.isArray(detail?.flag.evidence?.signal_evidence)
    ? (detail!.flag.evidence.signal_evidence as string[])
    : [];
  const reportSummary =
    typeof detail?.flag.evidence?.report_summary === "string"
      ? (detail!.flag.evidence.report_summary as string)
      : null;

  return (
    <Page>
      <PageHeader
        // Titled by what is being reviewed rather than by the page's own name, and
        // no longer prints the raw flag UUID at a reviewer.
        title={
          detail
            ? detail.flag.flag_type.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
            : "Flag review"
        }
        description="Nothing counts against the candidate until you uphold it."
        breadcrumb={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/fraud-review" />}>
                  Fraud review
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Flag</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={actionError ? () => setActionError(null) : retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !detail ? <CardListSkeleton /> : null}

      {detail && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold capitalize">
                {detail.flag.flag_type.replace(/_/g, " ")}
              </CardTitle>
              <CardDescription>
                Review the evidence trail and the candidate&apos;s dispute, if
                any.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <div className="border-b pb-3">
                <span className="font-semibold text-foreground">
                  Fraud Risk Report:
                </span>
                <p className="text-xs text-muted-foreground mt-1">
                  {reportSummary ?? "No narrative available."}
                </p>
              </div>

              <div className="border-b pb-3">
                <span className="font-semibold text-foreground">
                  Cited Evidence:
                </span>
                <ul className="text-xs text-muted-foreground mt-1 list-disc list-inside space-y-1">
                  {evidenceItems.length > 0 ? (
                    evidenceItems.map((item, i) => <li key={i}>{item}</li>)
                  ) : (
                    <li>No structured evidence items recorded.</li>
                  )}
                </ul>
              </div>

              {detail.dispute && (
                <div className="border-b pb-3">
                  <span className="font-semibold text-foreground">
                    Candidate Dispute Statement:
                  </span>
                  <p className="text-xs text-muted-foreground mt-1">
                    &quot;{detail.dispute.candidate_statement}&quot;
                  </p>
                </div>
              )}

              {detail.dispute_review_assist.available && (
                <div className="border-b pb-3 bg-card -mx-2 px-2 py-2 rounded-md">
                  <span className="font-semibold text-foreground">
                    Dispute Review Agent (assistive summary - not a
                    recommendation):
                  </span>
                  <p className="text-xs text-muted-foreground mt-1">
                    {detail.dispute_review_assist.candidate_context_summary}
                  </p>
                  <ul className="text-xs text-muted-foreground mt-1 list-disc list-inside space-y-1">
                    {detail.dispute_review_assist.points_of_agreement_or_conflict.map(
                      (point, i) => (
                        <li key={i}>{point}</li>
                      ),
                    )}
                  </ul>
                </div>
              )}

              {detail.flag.status === "raised" ||
              detail.flag.status === "under_review" ? (
                <div className="space-y-3 pt-2">
                  <label className="text-xs font-medium text-muted-foreground">
                    Review notes (required to uphold; optional to dismiss):
                  </label>
                  <Textarea
                    placeholder="Explain the basis for your decision..."
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                  />
                  <div className="flex gap-4">
                    <Button
                      onClick={() => handleAction("dismissed")}
                      variant="secondary"
                      disabled={submitting !== null}
                    >
                      {submitting === "dismissed"
                        ? "Dismissing…"
                        : "Dismiss Flag"}
                    </Button>
                    <Button
                      onClick={() => handleAction("upheld")}
                      variant="destructive"
                      disabled={submitting !== null || !reviewNotes.trim()}
                    >
                      {submitting === "upheld" ? "Upholding…" : "Uphold Flag"}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-success/10 border border-success/20 rounded-md text-sm mt-4">
                  <h4 className="font-semibold text-success capitalize">
                    Flag status: {resolution ?? detail.flag.status}
                  </h4>
                  <p className="text-xs text-muted-foreground mt-1">
                    Reviewer notes: {detail.flag.review_notes ?? "(none)"}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <div>
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold">
                  Audit Instructions
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground space-y-2 leading-relaxed">
                <p>
                  Weigh the evidence and any candidate dispute context. The AI
                  summary above is assistive only - it never recommends a
                  verdict.
                </p>
                <p>
                  An Uphold decision requires written notes and is the only
                  action that affects the candidate&apos;s authenticity score.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
