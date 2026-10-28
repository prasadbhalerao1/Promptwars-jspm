"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { Metric } from "@/components/common/Metric";
import { CodeEditor } from "@/components/CodeEditor";
import { MCQForm } from "@/components/MCQForm";
import {
  fetchAssessment,
  pollSubmissionGrading,
  submitAssessment,
  type CodingAssessmentSpec,
  type MCQAssessmentSpec,
  type SubmissionResponse,
  type TestResult,
} from "@/lib/api";
import { runHiddenTests } from "@/lib/pyodideRunner";

export default function CandidateAssessmentPage() {
  const params = useParams<{ id: string }>();
  const { getToken } = useAuth();

  const [code, setCode] = useState(
    "def solve_problem(n):\n # Write your Python code here\n return n * 2\n",
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [output, setOutput] = useState<TestResult[] | null>(null);
  const [running, setRunning] = useState(false);
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null);
  // Kept separate from the load error on purpose — see the guard below.
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchAssessment(token, params.id);
  }, [getToken, params.id]);

  const {
    data: assessment,
    error: loadError,
    loading,
    retry,
  } = useAsyncResource(fetcher, `candidate:assessment:${params.id}`);

  async function handleRunAndSubmit() {
    if (!assessment) return;
    setRunning(true);
    setSubmitError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");

      let result: SubmissionResponse | null = null;
      if (assessment.type === "coding") {
        const spec = assessment.spec as CodingAssessmentSpec;
        const results = await runHiddenTests(code, spec.hidden_tests);
        setOutput(results);
        result = await submitAssessment(token, assessment.id, {
          code_or_answers: { code },
          test_results: results,
        });
      } else if (assessment.type === "mcq") {
        result = await submitAssessment(token, assessment.id, {
          code_or_answers: { answers },
        });
      }

      if (result) {
        // Submit returns as soon as the row is stored; grading (static analysis +
        // LLM review) finishes in the background, so poll rather than rendering the
        // not-yet-graded null as a dash forever.
        setSubmission(result);
        toast.success("Assessment submitted", {
          description:
            result.grading_status === "processing"
              ? "Grading in progress…"
              : undefined,
        });
        if (result.grading_status === "processing") {
          const graded = await pollSubmissionGrading(token, result.id, {
            onUpdate: setSubmission,
          });
          setSubmission(graded);
          if (graded.grading_status === "failed") {
            setSubmitError(graded.grading_error ?? "Grading failed");
          }
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Submission failed";
      setSubmitError(message);
      toast.error(message);
    } finally {
      setRunning(false);
    }
  }

  const codingSpec =
    assessment?.type === "coding"
      ? (assessment.spec as CodingAssessmentSpec)
      : null;
  const mcqSpec =
    assessment?.type === "mcq" ? (assessment.spec as MCQAssessmentSpec) : null;

  return (
    <Page>
      <PageHeader
        title={
          assessment?.type === "mcq" ? "Quiz" : "Coding assessment"
        }
        description={
          assessment?.type === "coding"
            ? "Tests run locally in your browser via WebAssembly - your code is never executed on our servers."
            : "Answer the questions below."
        }
      />

      {/* Only a *load* failure blocks the page. A submit failure previously hit the
          same early return, which unmounted the editor and destroyed whatever the
          candidate had typed — on a timed assessment. Submit errors now render
          beside the editor and leave the work intact. */}
      {loadError ? (
        <SectionError message={loadError} onRetry={retry} retrying={loading} />
      ) : null}
      {loading && !assessment ? <CardListSkeleton /> : null}

      {assessment && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                {assessment.type === "coding" ? "Your solution" : "Questions"}
              </CardTitle>
              {codingSpec && (
                <CardDescription>
                  {codingSpec.problem_statement}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {assessment.type === "coding" && (
                <CodeEditor value={code} onChange={setCode} />
              )}
              {assessment.type === "mcq" && mcqSpec && (
                <MCQForm
                  spec={mcqSpec}
                  answers={answers}
                  onChange={setAnswers}
                />
              )}
              {submitError && (
                <p role="alert" className="text-body text-destructive">
                  {submitError}
                </p>
              )}
              <Button
                onClick={handleRunAndSubmit}
                pending={running}
                disabled={!!submission}
              >
                {running
                  ? "Running…"
                  : submission
                    ? "Submitted"
                    : assessment.type === "coding"
                      ? "Run tests & submit"
                      : "Submit"}
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {codingSpec && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold">
                    Constraints
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5 text-meta text-muted-foreground">
                  <p>
                    {codingSpec.hidden_tests.length} hidden test
                    {codingSpec.hidden_tests.length === 1 ? "" : "s"}
                  </p>
                  <p>
                    Your function must be named{" "}
                    <code className="rounded bg-muted px-1 py-0.5 font-mono">
                      solve_problem
                    </code>
                  </p>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold">
                  Result
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {output && (
                  <ul className="space-y-1">
                    {output.map((r) => (
                      <li
                        key={r.test_name}
                        className="flex items-center justify-between gap-2 text-meta"
                      >
                        <span className="truncate font-mono text-foreground">
                          {r.test_name}
                        </span>
                        <span
                          className={
                            r.passed ? "text-success" : "text-destructive"
                          }
                        >
                          {r.passed ? "pass" : "fail"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {submission ? (
                  <div aria-live="polite" className="space-y-1">
                    {submission.grading_status === "processing" ? (
                      <p className="text-body text-muted-foreground">
                        Submitted - grading your answer…
                      </p>
                    ) : submission.grading_status === "failed" ? (
                      <p className="text-body text-destructive">
                        Grading failed. Your submission was saved.
                      </p>
                    ) : (
                      <Metric
                        label="Score"
                        value={
                          submission.score === null ||
                          submission.score === undefined
                            ? "Not recorded"
                            : `${submission.score.toFixed(0)}/100`
                        }
                      />
                    )}
                    {submission.test_results?.rationale && (
                      <p className="text-meta leading-relaxed text-muted-foreground">
                        {submission.test_results.rationale}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-meta text-muted-foreground">
                    Run and submit to see your result.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
