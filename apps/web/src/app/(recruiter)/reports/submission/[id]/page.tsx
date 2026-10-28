"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { Check, X } from "lucide-react";

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
import { fetchSubmission } from "@/lib/api";

export default function RecruiterSubmissionReportPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchSubmission(token, params.id);
  }, [getToken, params.id]);

  const {
    data: submission,
    error,
    loading,
    retry,
  } = useAsyncResource(fetcher, `recruiter:submission:${params.id}`);

  const testResults = submission?.test_results?.results ?? [];
  const passed = testResults.filter((r) => r.passed).length;

  return (
    <Page>
      <PageHeader
        title="Assessment submission"
        description="Test results, static analysis, and code review for this submission."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !submission ? <CardListSkeleton /> : null}

      {submission && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <Card className="space-y-4 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Results
              </CardTitle>
              <CardDescription>
                {testResults.length > 0
                  ? `${passed} of ${testResults.length} tests passed.`
                  : "No test results recorded for this submission."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* The score was previously always styled `text-success` regardless of
                  its value, so a 12/100 rendered in the same teal as a 98/100. */}
              <Metric
                label="Score"
                value={
                  submission.score === null || submission.score === undefined
                    ? "Not recorded"
                    : `${submission.score.toFixed(0)}/100`
                }
              />

              {testResults.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-body font-medium text-foreground">
                    Tests
                  </h2>
                  <ul className="space-y-1">
                    {testResults.map((r) => (
                      <li
                        key={r.test_name}
                        className="flex items-center gap-2 text-body"
                      >
                        {r.passed ? (
                          <Check
                            aria-hidden
                            className="size-3.5 shrink-0 text-success"
                          />
                        ) : (
                          <X
                            aria-hidden
                            className="size-3.5 shrink-0 text-destructive"
                          />
                        )}
                        <span className="font-mono text-meta text-foreground">
                          {r.test_name}
                        </span>
                        <span className="sr-only">
                          {r.passed ? "passed" : "failed"}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {submission.test_results?.rationale && (
                    <p className="text-meta leading-relaxed text-muted-foreground">
                      {submission.test_results.rationale}
                    </p>
                  )}
                </div>
              )}

              {submission.llm_review && (
                <div className="space-y-3 border-t border-border pt-4">
                  <h2 className="text-body font-medium text-foreground">
                    Code review
                  </h2>
                  <div className="grid grid-cols-2 gap-3">
                    <Metric
                      label="Readability"
                      value={
                        submission.llm_review.readability?.toFixed(0) ?? "Not recorded"
                      }
                    />
                    <Metric
                      label="Architecture"
                      value={
                        submission.llm_review.architecture?.toFixed(0) ?? "Not recorded"
                      }
                    />
                  </div>
                  {submission.llm_review.red_flags.length > 0 && (
                    <ul className="list-inside list-disc space-y-1 text-meta text-destructive">
                      {submission.llm_review.red_flags.map((flag, i) => (
                        <li key={i}>{flag}</li>
                      ))}
                    </ul>
                  )}
                  {submission.llm_review.rationale && (
                    <p className="text-meta leading-relaxed text-muted-foreground">
                      {submission.llm_review.rationale}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <div>
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold">
                  Static analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-meta leading-relaxed text-muted-foreground">
                {submission.static_analysis?.skipped ? (
                  <p>{submission.static_analysis.skipped}</p>
                ) : (
                  <>
                    {submission.static_analysis?.radon && (
                      <p>
                        Average complexity:{" "}
                        <span className="text-foreground">
                          {String(
                            submission.static_analysis.radon.avg_complexity ??
                              "Not recorded",
                          )}
                        </span>
                      </p>
                    )}
                    {submission.static_analysis?.bandit && (
                      <p>
                        Security findings:{" "}
                        <span className="text-foreground">
                          {String(
                            submission.static_analysis.bandit.issue_count ?? 0,
                          )}
                        </span>
                      </p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
