"use client";

import { useAuth } from "@/components/AuthProvider";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AIContentSignalBadge } from "@/components/AIContentSignalBadge";
import { PitchScoreRadarChart } from "@/components/PitchScoreRadarChart";
import { PlagiarismMatchList } from "@/components/PlagiarismMatchList";
import { SlideViewer } from "@/components/SlideViewer";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import {
  AlertCircle,
  CheckCircle2,
  Compass,
  HelpCircle,
  Layers,
  XCircle,
} from "lucide-react";
import {
  PITCH_SCORE_LABELS,
  pollPresentationReport,
  type PresentationReportResponse,
} from "@/lib/api";

// Lives OUTSIDE any (role) route group — same reasoning as the shared /dashboard route
// (.agents/decisions.md): doc/SRS/04 §1/§2 says this module is "fully self-contained"
// and viewable by candidates, judges, recruiters, and investors alike, not just the
// uploader, so it can't live inside the (candidate)-only group's role guard.
export default function PitchDeckReportPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { getToken } = useAuth();
  const { me, isLoaded, isSignedIn, error: meError } = useCurrentUser();
  const [report, setReport] = useState<PresentationReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }
    if (!me) return;
    if (me.onboarding_required || !me.profile) {
      router.replace("/onboarding");
      return;
    }

    const controller = new AbortController();

    void (async () => {
      try {
        const token = await getToken();
        if (!token) throw new Error("No session token");
        await pollPresentationReport(token, params.id, {
          signal: controller.signal,
          onUpdate: (data) => {
            if (!controller.signal.aborted) setReport(data);
          },
        });
      } catch (err) {
        if (!controller.signal.aborted)
          setError(
            err instanceof Error ? err.message : "Failed to load report",
          );
      }
    })();

    return () => controller.abort();
  }, [isLoaded, isSignedIn, me, getToken, router, params.id]);

  const blockingError = meError ?? error;
  if (blockingError) {
    return (
      <Page width="reading">
        <PageHeader title="Pitch deck report" />
        <SectionError
          message={blockingError}
          onRetry={() => window.location.reload()}
          retrying={false}
        />
      </Page>
    );
  }

  if (!report) {
    return (
      <Page width="reading">
        <PageHeader title="Pitch deck report" />
        <CardListSkeleton />
      </Page>
    );
  }

  if (report.status === "failed") {
    return (
      <Page width="reading">
        <PageHeader
          title="Analysis failed"
          description="This deck could not be processed. Try re-uploading it, or check that the file format is supported."
        />
      </Page>
    );
  }

  if (report.status === "processing") {
    return (
      <Page width="reading">
        <PageHeader title="Analysing your deck…" />
        <div aria-live="polite" className="space-y-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full w-full animate-pulse rounded-full bg-primary" />
          </div>
          <p className="text-body leading-relaxed text-muted-foreground">
            Extracting slides, evaluating problem alignment, checking requirement coverage,
            scoring innovation and feasibility, and checking for plagiarism.
          </p>
        </div>
      </Page>
    );
  }

  return (
    <Page width="reading" className="space-y-6">
      <PageHeader
        title="Pitch deck report"
        description="Evidence-backed evaluation with problem requirement coverage, rubric justifications, and slide citations."
      />

      {/* Challenge / Problem Statement Context */}
      {report.problem_statement ? (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base font-medium text-foreground">
                <Compass className="size-4 text-primary" />
                Supplied Challenge Brief & Problem Statement
              </CardTitle>
              <Badge variant="outline" className="border-primary/30 text-primary">
                Context-Aligned
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/90 bg-background/50 p-3 rounded border border-border/50">
              {report.problem_statement}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-warning/20 bg-warning/5">
          <CardContent className="flex items-start gap-3 p-4">
            <AlertCircle className="size-5 shrink-0 text-warning mt-0.5" />
            <div>
              <p className="text-sm font-medium text-warning">
                Generic Presentation Evaluation
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                No problem statement or challenge brief was supplied with this deck. Problem alignment has been evaluated against general startup / hackathon presentation standards without inventing unverified constraints.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Overall Score & Radar Chart */}
      <Card>
        <CardContent className="grid gap-6 p-5 sm:grid-cols-[auto_1fr] sm:items-center">
          <div>
            <p className="text-meta font-medium text-muted-foreground">
              Overall Pitch Score
            </p>
            <div className="mt-1 flex items-baseline gap-1.5">
              {report.overall_pitch_score === null ? (
                <span className="text-section text-muted-foreground">
                  Not yet computable
                </span>
              ) : (
                <>
                  <span
                    data-numeric
                    className="font-mono text-title font-semibold text-foreground"
                  >
                    {report.overall_pitch_score.toFixed(1)}
                  </span>
                  <span className="text-body text-muted-foreground">/ 10</span>
                </>
              )}
            </div>
            <p className="mt-2 text-xs text-muted-foreground max-w-xs">
              Calculated from rubric weights across problem alignment, solution coverage, feasibility, validation, and presentation quality.
            </p>
          </div>
          <PitchScoreRadarChart scores={report.scores} />
        </CardContent>
      </Card>

      {/* Requirement Coverage Matrix */}
      {report.requirement_coverage && report.requirement_coverage.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Layers className="size-4 text-primary" />
                  Requirement Coverage Matrix
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-1">
                  Traceable mapping of challenge requirements to exact slide evidence
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-xs">
                {report.requirement_coverage.filter((r) => r.status === "met").length} of {report.requirement_coverage.length} Met
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {report.requirement_coverage.map((req) => (
              <div key={req.id} className="rounded-lg border border-border p-4 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-muted text-muted-foreground">
                      {req.id}
                    </span>
                    <span className="text-sm font-medium text-foreground">{req.requirement}</span>
                  </div>
                  {req.status === "met" && (
                    <Badge className="bg-success/10 text-success border border-success/20">
                      <CheckCircle2 className="size-3 mr-1" /> Met
                    </Badge>
                  )}
                  {req.status === "partially_met" && (
                    <Badge className="bg-warning/10 text-warning border border-warning/20">
                      <AlertCircle className="size-3 mr-1" /> Partially Met
                    </Badge>
                  )}
                  {req.status === "not_met" && (
                    <Badge variant="destructive">
                      <XCircle className="size-3 mr-1" /> Not Met
                    </Badge>
                  )}
                  {req.status === "unclear" && (
                    <Badge variant="outline">
                      <HelpCircle className="size-3 mr-1" /> Unclear
                    </Badge>
                  )}
                </div>

                {req.relevant_slides && req.relevant_slides.length > 0 ? (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs text-muted-foreground">Cited Slides:</span>
                    {req.relevant_slides.map((s) => (
                      <a
                        key={s}
                        href={`#slide-${s}`}
                        className="inline-flex items-center text-xs font-mono font-medium px-2 py-0.5 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                      >
                        Slide {s}
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">No slide visibly addressed this requirement.</p>
                )}

                {req.evidence_excerpt && (
                  <p className="text-xs text-muted-foreground bg-muted/40 p-2.5 rounded border border-border/50">
                    <span className="font-medium text-foreground">Extracted Evidence: </span>
                    {req.evidence_excerpt}
                  </p>
                )}

                {req.identified_gaps && req.identified_gaps.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-warning">Gaps & Assumptions:</p>
                    <ul className="list-disc list-inside text-xs text-muted-foreground">
                      {req.identified_gaps.map((gap, i) => (
                        <li key={i}>{gap}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {req.recommendation && (
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Recommendation: </span>
                    {req.recommendation}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 5-Pillar Rubric Breakdown with Slide Citations */}
      {report.rubric_breakdown && (
        <Card>
          <CardHeader>
            <CardTitle className="font-heading">5-Pillar Rubric Breakdown</CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-1">
              Structured evaluation with slide citations and transparent deduction rationales
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(report.rubric_breakdown).map(([pillarKey, p]) => (
              <div key={pillarKey} className="rounded-lg border border-border p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium capitalize text-foreground">
                      {pillarKey.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Weight: {(p.weight * 100).toFixed(0)}% • Contribution: {p.weighted_score.toFixed(2)} pts
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-base font-semibold text-foreground">
                      {p.score.toFixed(1)}
                    </span>
                    <span className="text-xs text-muted-foreground"> / 10</span>
                  </div>
                </div>

                {p.slide_citations && p.slide_citations.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs text-muted-foreground">Slide Evidence:</span>
                    {p.slide_citations.map((s) => (
                      <a
                        key={s}
                        href={`#slide-${s}`}
                        className="inline-flex items-center text-xs font-mono font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      >
                        Slide {s}
                      </a>
                    ))}
                  </div>
                )}

                {p.findings && p.findings.length > 0 && (
                  <ul className="list-disc list-inside text-xs text-muted-foreground space-y-0.5">
                    {p.findings.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}

                {p.deductions && p.deductions.length > 0 && (
                  <div className="mt-2 rounded bg-destructive/10 p-2.5 border border-destructive/20 text-xs text-destructive space-y-1">
                    <span className="font-medium">Specific Deductions:</span>
                    <ul className="list-disc list-inside space-y-0.5">
                      {p.deductions.map((d, i) => (
                        <li key={i}>{d}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Legacy / Standard Score breakdown fallback */}
      {!report.rubric_breakdown && (
        <Card>
          <CardHeader>
            <CardTitle className="font-heading">Score breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(PITCH_SCORE_LABELS).map(([key, label]) => {
              const sub = report.scores[key];
              const wasRenormalized = report.renormalized_scores.includes(key);
              return (
                <div
                  key={key}
                  className="border-b border-border pb-2 last:border-0 last:pb-0"
                >
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm font-medium text-foreground">
                      {label}
                    </span>
                    <span className="text-sm tabular-nums text-muted-foreground">
                      {sub?.value !== null && sub?.value !== undefined
                        ? sub.value.toFixed(1)
                        : wasRenormalized
                          ? "Not scored, weight redistributed"
                          : "Not yet computable"}
                    </span>
                  </div>
                  {sub?.rationale && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {sub.rationale}
                    </p>
                  )}
                  {sub?.gaps && sub.gaps.length > 0 && (
                    <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                      {sub.gaps.map((gap: string) => (
                        <li key={gap}>{gap}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-sm text-foreground">
            {report.summary ?? "No summary available."}
          </p>
        </CardContent>
      </Card>

      {report.suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="font-heading">
              Improvement suggestions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-inside list-disc space-y-1 text-sm text-foreground">
              {report.suggestions.map((s: string) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">AI-content signal</CardTitle>
        </CardHeader>
        <CardContent>
          <AIContentSignalBadge signal={report.ai_content_signal} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Plagiarism matches</CardTitle>
        </CardHeader>
        <CardContent>
          <PlagiarismMatchList
            matches={report.plagiarism_matches}
            checked={report.plagiarism_checked}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Slides</CardTitle>
        </CardHeader>
        <CardContent>
          <SlideViewer slides={report.slides} />
        </CardContent>
      </Card>
    </Page>
  );
}
