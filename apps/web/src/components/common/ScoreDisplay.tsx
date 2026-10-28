"use client";

import { Info } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { EvidenceConfidence, SubScore } from "@/lib/api";

/** Below this share of resolved signals the score reflects a sparse profile rather than
 * a weak candidate.
 *
 * This is the only definition. `EvidenceConfidence` in packages/shared_schemas mentions a
 * "50% confidence threshold", but that is prose in a docstring, not a constant — the API
 * ships the raw `available_signals`/`expected_signals` and takes no action at any cutoff.
 * The previous comment here claimed to mirror a backend threshold, which would have sent
 * a future reader looking for something to keep in sync that does not exist. Presentation
 * is genuinely the frontend's call, so it lives here. */
const SPARSE_PROFILE_THRESHOLD = 0.5;

export function confidenceRatio(
  confidence: EvidenceConfidence | null | undefined,
): number | null {
  if (!confidence || !confidence.expected_signals) return null;
  return confidence.available_signals / confidence.expected_signals;
}

/** Confidence, expressed as coverage of expected evidence.
 *
 * Deliberately never uses `--destructive`: low confidence means we have not gathered
 * enough evidence yet, not that the candidate scored badly. Colouring it red would
 * invite exactly the misreading the backend warns against. */
export function ConfidenceBadge({
  confidence,
  className,
}: {
  confidence: EvidenceConfidence | null | undefined;
  className?: string;
}) {
  const ratio = confidenceRatio(confidence);
  if (ratio === null || !confidence) return null;

  const sparse = ratio < SPARSE_PROFILE_THRESHOLD;

  return (
    <Badge
      variant="outline"
      className={cn("gap-1 font-normal", sparse && "text-warning", className)}
    >
      <span data-numeric>
        {confidence.available_signals}/{confidence.expected_signals} signals
      </span>
      {sparse ? <span>· sparse profile</span> : null}
    </Badge>
  );
}

interface ScoreDisplayProps {
  /** `null` means not yet computable — rendered as such, never as 0. */
  value: number | null | undefined;
  label?: string;
  confidence?: EvidenceConfidence | null;
  computedAt?: string | null;
  size?: "sm" | "lg";
  className?: string;
}

/** A score, with the context that makes it honest.
 *
 * A bare number invites over-reading. This keeps the value, its evidence coverage and
 * its age together, and distinguishes "not yet computable" from a real low score. */
export function ScoreDisplay({
  value,
  label,
  confidence,
  computedAt,
  size = "lg",
  className,
}: ScoreDisplayProps) {
  const pending = value === null || value === undefined;

  return (
    <div className={cn("space-y-1", className)}>
      {label ? (
        <p className="text-meta text-muted-foreground">{label}</p>
      ) : null}
      <div className="flex items-baseline gap-2">
        {pending ? (
          <span className="text-body text-muted-foreground">
            Not yet computable
          </span>
        ) : (
          <span
            data-numeric
            className={cn(
              "font-medium tabular-nums text-foreground",
              size === "lg" ? "text-title" : "text-section",
            )}
          >
            {value.toFixed(1)}
          </span>
        )}
        {!pending && confidence ? (
          <ConfidenceBadge confidence={confidence} />
        ) : null}
      </div>
      {computedAt ? (
        <p className="text-meta text-muted-foreground">
          Computed {new Date(computedAt).toLocaleDateString()}
        </p>
      ) : null}
    </div>
  );
}

/** Surfaces a sub-score's rationale and the agent runs behind it.
 *
 * Provenance is the product here — the backend records `evidence` and `rationale` on
 * every sub-score, and hiding them would make the score less trustworthy, not tidier. */
export function EvidencePopover({
  label,
  subScore,
}: {
  label: string;
  subScore: SubScore | null | undefined;
}) {
  if (!subScore?.rationale && !subScore?.evidence?.length) return null;

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Why ${label} scored this way`}
            className="rounded-sm text-muted-foreground outline-none transition-colors duration-(--animate-duration-fast) hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Info className="size-3.5" />
          </button>
        }
      />
      <PopoverContent align="start" className="w-80 space-y-2">
        <p className="text-meta font-medium text-foreground">{label}</p>
        {subScore.rationale ? (
          <p className="text-meta leading-relaxed text-muted-foreground">
            {subScore.rationale}
          </p>
        ) : null}
        {subScore.evidence?.length ? (
          <div className="space-y-1 pt-1">
            <p className="text-meta text-muted-foreground">Evidence</p>
            <ul className="space-y-0.5">
              {subScore.evidence.map((id) => (
                <li
                  key={id}
                  className="truncate font-mono text-meta text-muted-foreground"
                >
                  {id}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
