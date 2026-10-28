"use client";

import { Info } from "lucide-react";

import {
  ConfidenceBadge,
  confidenceRatio,
} from "@/components/common/ScoreDisplay";
import {
  SUB_SCORE_LABELS,
  type TalentScoreResponse,
} from "@/lib/api";

/** The Talent Score, with the context that makes it honest.
 *
 * This replaces a bare `overall.toFixed(1)` in the dashboard header. The backend records
 * a confidence, a computed timestamp, a rationale and the agent runs behind every
 * sub-score, and none of it was reaching the screen: `ScoreDisplay`, `EvidencePopover`
 * and `ConfidenceBadge` existed with zero importers while 33 call sites rendered
 * unattributable numbers.
 *
 * The conventions here are the product's, not decoration:
 *   - a `null` sub-score reads "Not yet computable", never 0 and never a dash, because
 *     "no evidence" and "bad evidence" are different findings;
 *   - low confidence reads *sparse profile* and is never styled with `--destructive`,
 *     since a cold-start profile is not a weak candidate;
 *   - renormalized sub-scores say so, rather than silently redistributing weight.
 */
export function TalentScorePanel({ score }: { score: TalentScoreResponse }) {
  const ratio = confidenceRatio(score.confidence);
  const sparse = ratio !== null && ratio < 0.5;

  const entries = Object.entries(score.sub_scores).sort(
    ([, a], [, b]) => (b.value ?? -1) - (a.value ?? -1),
  );

  return (
    <section
      aria-label="Talent Score"
      className="rounded-lg bg-card p-5 shadow-flat"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-section font-semibold text-foreground">
            Talent Score
          </h2>
          <p className="mt-0.5 text-meta text-muted-foreground">
            Computed {new Date(score.computed_at).toLocaleDateString()} using{" "}
            {score.score_version}
          </p>
        </div>
        <ConfidenceBadge confidence={score.confidence} />
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        {score.overall === null ? (
          <span className="text-section text-muted-foreground">
            Not yet computable
          </span>
        ) : (
          <>
            <span
              data-numeric
              className="font-mono text-title font-semibold text-foreground"
            >
              {score.overall.toFixed(1)}
            </span>
            <span className="text-body text-muted-foreground">/ 100</span>
          </>
        )}
      </div>

      {sparse ? (
        // Deliberately warning, never destructive: this says "we have not gathered
        // enough evidence yet", not "this candidate scored badly".
        <p className="mt-3 flex items-start gap-2 rounded-md bg-warning/10 p-3 text-meta leading-relaxed text-warning">
          <Info aria-hidden className="mt-px size-3.5 shrink-0" />
          <span>
            This score rests on a sparse profile rather than a weak record.
            Connect more evidence to raise its confidence.
          </span>
        </p>
      ) : null}

      <div className="mt-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Top Evidenced Strengths
        </p>
        <div className="space-y-2.5">
          {entries.filter(([, sub]) => sub.value !== null).slice(0, 3).map(([key, sub]) => (
            <div key={key} className="flex items-center justify-between p-2.5 rounded-lg border border-border/70 bg-muted/20">
              <span className="text-xs font-medium text-foreground">
                {SUB_SCORE_LABELS[key] ?? key}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-semibold text-foreground">
                  {sub.value?.toFixed(1)}
                </span>
                <span className="text-xs text-muted-foreground font-mono">/100</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
