"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { Metric } from "@/components/common/Metric";
import { fetchInterviewReport } from "@/lib/api";

export default function RecruiterInterviewReportPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();

  // Was a hand-rolled useEffect/useState pair whose only failure state was a bare
  // full-page string with no way to retry. useAsyncResource brings the same
  // retry/backoff every other route already had.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchInterviewReport(token, params.id);
  }, [getToken, params.id]);

  const {
    data: report,
    error,
    loading,
    retry,
  } = useAsyncResource(fetcher, `recruiter:interview-report:${params.id}`);

  return (
    <Page>
      <PageHeader
        title="Interview report"
        description="Full transcript, ratings, and the reasoning behind them."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !report ? <CardListSkeleton /> : null}

      {report && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <Card className="space-y-4 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Transcript
              </CardTitle>
              {/* Was "no audio was recorded (doc 03 §3)" — the fact matters to a
                  recruiter, the internal document reference does not. */}
              <CardDescription>
                Text only - no audio is ever recorded.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="max-h-96 space-y-3 overflow-y-auto rounded-lg p-4 shadow-flat">
                {report.transcript.map((t) => (
                  <div key={t.turn_index} className="space-y-0.5">
                    <p className="text-meta font-medium text-muted-foreground">
                      {t.role === "agent" ? "Interviewer" : "Candidate"}
                    </p>
                    <p className="text-body leading-relaxed text-foreground">
                      {t.text}
                    </p>
                  </div>
                ))}
              </div>
              <div className="border-t border-border pt-3">
                <h2 className="text-body font-medium text-foreground">
                  Hiring recommendation
                </h2>
                <p className="mt-1 text-body leading-relaxed text-muted-foreground">
                  {report.hiring_recommendation ?? "Not yet generated."}
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {/* Ratings are legitimately null until the report is generated, so each
                renders "Not recorded" rather than a zero that would read as a bad score. */}
            <Metric
              label="Technical"
              value={
                report.technical_rating === null ||
                report.technical_rating === undefined
                  ? "Not recorded"
                  : `${report.technical_rating.toFixed(0)}/100`
              }
            />
            <Metric
              label="Communication"
              value={
                report.communication_rating === null ||
                report.communication_rating === undefined
                  ? "Not recorded"
                  : `${report.communication_rating.toFixed(0)}/100`
              }
            />
            <Metric
              label="Response confidence"
              value={
                report.response_confidence_signal === null ||
                report.response_confidence_signal === undefined
                  ? "Not recorded"
                  : `${report.response_confidence_signal.toFixed(0)}/100`
              }
              hint="From transcript text only"
            />
            <p className="text-meta leading-relaxed text-muted-foreground">
              Confidence and communication are derived entirely from the text of
              the transcript - hedging language and specificity. Never voice
              biometrics or emotion inference.
            </p>
          </div>
        </div>
      )}
    </Page>
  );
}
