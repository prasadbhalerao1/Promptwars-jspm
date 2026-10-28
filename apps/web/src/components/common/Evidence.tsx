"use client";

import { Info } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/** The evidence model, as a cross-product primitive.
 *
 * TRACE's whole claim is that a number is only trustworthy when you can see what produced
 * it. That was true of the marketing page and almost untrue of the application: an audit
 * found `ScoreDisplay` with **zero render sites** while roughly twenty screens rendered
 * bare `toFixed()` numbers - a recruiter reading `8.4` on a leaderboard could not tell
 * whether it came from twelve signals or two.
 *
 * `ScoreDisplay` was not adopted because it only fits one shape: a `/100` float carrying
 * an `EvidenceConfidence` object. Hackathon composite scores, interview ratings, judge
 * scores and contribution shares have none of that. So this module takes the same idea and
 * makes it fit every call site, at three deliberate levels of weight:
 *
 * - **`ScoreValue`** (level 1) - a number with its source named beside it. Cheap enough to
 *   put in a list row or a table cell, which is where most scores in this product live.
 * - **`EvidenceNote`** (level 2) - inline, expandable provenance for a figure that carries
 *   a decision.
 * - **`EvidencePanel`** (level 3) - the full breakdown, for a screen whose subject *is*
 *   the score.
 *
 * Choosing a level is a judgement about importance. Wrapping every number in a panel
 * would bury the product in explanation and make it slower to scan, which is the opposite
 * of the goal.
 *
 * Vocabulary is fixed here on purpose. One word per concept - **score**, **confidence**,
 * **evidence**, **source**, **recommendation**, **review**, **verified** - because the
 * audit found three different phrasings for "we could not compute this"
 * (`"Not recorded"`, `"Not scored"`, and an inline null branch) across screens a single
 * user visits in one session.
 */

/** The canonical phrasing for an absent value.
 *
 * Never `N/A` (a design-system rule bans it) and never `0`: a score that could not be
 * computed and a score of zero are different findings, and rendering the first as the
 * second is a lie about a person. */
export const NOT_COMPUTABLE = "Not yet computable";

export type Strength = "high" | "moderate" | "limited";

/** How much evidence stands behind a figure.
 *
 * Deliberately never `--destructive`. Limited evidence means TRACE has not gathered enough
 * yet, not that the subject is bad - colouring it red invites exactly the misreading the
 * product exists to prevent. */
export function strengthOf(available: number, expected: number): Strength {
  if (!expected) return "limited";
  const ratio = available / expected;
  if (ratio >= 0.75) return "high";
  if (ratio >= 0.5) return "moderate";
  return "limited";
}

const STRENGTH_LABEL: Record<Strength, string> = {
  high: "High",
  moderate: "Moderate",
  limited: "Limited",
};

/** Level 1: a value with its source.
 *
 * The workhorse. Sized to sit inside a list row or a badge slot without changing the
 * row's rhythm, because most scores in this product appear in lists.
 */
export function ScoreValue({
  value,
  /** Where the number came from: `AI interview`, `Judge panel`, `12 signals`. */
  source,
  /** Appended to the number, e.g. `%` or `/100`. */
  suffix,
  decimals = 1,
  size = "sm",
  className,
}: {
  value: number | null | undefined;
  source?: string;
  suffix?: string;
  decimals?: number;
  size?: "sm" | "lg";
  className?: string;
}) {
  const pending = value === null || value === undefined;

  return (
    <div className={cn("min-w-0", className)}>
      {pending ? (
        <p className="text-meta text-muted-foreground">{NOT_COMPUTABLE}</p>
      ) : (
        <p
          data-numeric
          className={cn(
            "font-medium tabular-nums text-foreground",
            size === "lg" ? "text-title" : "text-section",
          )}
        >
          {value.toFixed(decimals)}
          {suffix ? (
            <span className="text-meta font-normal text-muted-foreground">
              {suffix}
            </span>
          ) : null}
        </p>
      )}
      {source ? (
        <p className="truncate text-meta text-muted-foreground">{source}</p>
      ) : null}
    </div>
  );
}

/** How much evidence stands behind a figure, as a compact readout.
 *
 * Text rather than a coloured pill: at limited strength a pill reads as a warning about
 * the person instead of a statement about our coverage. */
export function EvidenceStrength({
  available,
  expected,
  className,
}: {
  available: number;
  expected: number;
  className?: string;
}) {
  if (!expected) return null;
  const strength = strengthOf(available, expected);

  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1.5 text-meta",
        strength === "limited" ? "text-warning" : "text-muted-foreground",
        className,
      )}
    >
      <span data-numeric className="tabular-nums">
        {available}/{expected} signals
      </span>
      <span aria-hidden>·</span>
      <span>{STRENGTH_LABEL[strength]} confidence</span>
    </span>
  );
}

export interface EvidenceItem {
  /** What was read: `GitHub`, `Repository #4`, `Interview Q04`. */
  source: string;
  /** What it showed. */
  detail?: string;
}

/** Level 2: inline, expandable provenance.
 *
 * For a figure that carries a decision but does not own the screen. Collapsed by default
 * so a dense list stays scannable; the trigger names what it will reveal rather than
 * being a bare icon, so it is usable without hovering to find out.
 */
export function EvidenceNote({
  label,
  rationale,
  items,
}: {
  /** What the evidence explains, for the accessible name. */
  label: string;
  rationale?: string | null;
  items?: readonly EvidenceItem[];
}) {
  const hasItems = Boolean(items?.length);
  if (!rationale && !hasItems) return null;

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Evidence behind ${label}`}
            className="inline-flex items-center gap-1 rounded-sm text-meta text-muted-foreground outline-none transition-colors duration-(--animate-duration-fast) hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Info aria-hidden className="size-3.5" />
            Evidence
          </button>
        }
      />
      <PopoverContent align="start" className="w-80 space-y-2.5">
        <p className="text-meta font-medium text-foreground">{label}</p>
        {rationale ? (
          <p className="text-meta leading-relaxed text-muted-foreground">
            {rationale}
          </p>
        ) : null}
        {hasItems ? (
          <div className="space-y-1.5">
            <p className="text-meta text-muted-foreground">Sources</p>
            <ul className="space-y-1">
              {items!.map((item) => (
                <li key={item.source} className="min-w-0">
                  <span className="block truncate text-meta text-foreground">
                    {item.source}
                  </span>
                  {item.detail ? (
                    <span className="block truncate text-meta text-muted-foreground">
                      {item.detail}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

export interface ScoreDimension {
  label: string;
  value: number | null;
  /** Where this dimension came from, shown beneath it. */
  source?: string;
}

/** Level 3: the full reading of a score.
 *
 * For a screen whose subject *is* the figure - a talent profile, an interview report, a
 * pitch analysis. Headline, then the dimensions that produced it, then the evidence
 * standing behind the whole thing, in that order, because that is the order the question
 * is actually asked in: what is it, what is it made of, why should I believe it.
 */
export function EvidencePanel({
  label,
  value,
  suffix,
  decimals = 1,
  dimensions,
  confidence,
  recommendation,
  computedAt,
  className,
}: {
  label: string;
  value: number | null | undefined;
  suffix?: string;
  decimals?: number;
  dimensions?: readonly ScoreDimension[];
  confidence?: { available: number; expected: number } | null;
  /** The conclusion drawn, if the module draws one. */
  recommendation?: string | null;
  computedAt?: string | null;
  className?: string;
}) {
  const pending = value === null || value === undefined;
  const measured = dimensions?.filter((d) => d.value !== null) ?? [];

  return (
    <div className={cn("space-y-5", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <p className="text-meta font-medium tracking-wide text-muted-foreground uppercase">
            {label}
          </p>
          {pending ? (
            <p className="mt-1.5 text-section text-muted-foreground">
              {NOT_COMPUTABLE}
            </p>
          ) : (
            <p
              data-numeric
              className="mt-1 text-figure font-semibold tabular-nums text-foreground"
            >
              {value.toFixed(decimals)}
              {suffix ? (
                <span className="text-section font-normal text-muted-foreground">
                  {suffix}
                </span>
              ) : null}
            </p>
          )}
        </div>
        {confidence ? (
          <EvidenceStrength
            available={confidence.available}
            expected={confidence.expected}
          />
        ) : null}
      </div>

      {measured.length > 0 ? (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-4">
          {dimensions!.map(({ label: dim, value: dimValue, source }) => (
            <div key={dim} className="min-w-0 border-t border-border pt-3">
              <dt className="truncate text-meta text-muted-foreground">{dim}</dt>
              {dimValue === null ? (
                <dd className="mt-0.5 text-meta text-muted-foreground">
                  {NOT_COMPUTABLE}
                </dd>
              ) : (
                <>
                  <dd
                    data-numeric
                    className="mt-0.5 text-section font-medium tabular-nums text-foreground"
                  >
                    {dimValue.toFixed(0)}
                  </dd>
                  <div
                    aria-hidden
                    className="mt-2 h-0.5 w-full overflow-hidden rounded-full bg-surface-sunken"
                  >
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{
                        width: `${Math.max(0, Math.min(100, dimValue))}%`,
                      }}
                    />
                  </div>
                </>
              )}
              {source ? (
                <p className="mt-1.5 truncate text-meta text-muted-foreground">
                  {source}
                </p>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}

      {recommendation ? (
        <div className="border-t border-border pt-4">
          <p className="text-meta font-medium tracking-wide text-muted-foreground uppercase">
            Recommendation
          </p>
          <p className="mt-1 text-section font-medium text-foreground">
            {recommendation}
          </p>
        </div>
      ) : null}

      {computedAt ? (
        <p className="text-meta text-muted-foreground">
          Computed {new Date(computedAt).toLocaleDateString()}
        </p>
      ) : null}
    </div>
  );
}
