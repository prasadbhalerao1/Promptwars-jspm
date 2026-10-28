import { cn } from "@/lib/utils";

/** The components behind a match percentage.
 *
 * A bare "94% match" invites a decision it cannot support: a recruiter needs to know
 * which of skill overlap, project relevance, experience or verified evidence produced
 * it. The backend already returns every component on `MatchScoreWithCandidateResponse`,
 * so a percentage should never render without them.
 *
 * `null` reads "not measured" rather than 0, because a component with no evidence and a
 * component that scored badly are different findings.
 */
export interface MatchComponent {
  label: string;
  value: number | null;
}

export function MatchBreakdown({
  components,
  className,
}: {
  components: MatchComponent[];
  className?: string;
}) {
  const measured = components.filter((c) => c.value !== null);
  if (measured.length === 0) return null;

  return (
    <dl
      className={cn(
        "grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4",
        className,
      )}
    >
      {components.map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="truncate text-meta text-muted-foreground">{label}</dt>
          {value === null ? (
            <dd className="text-meta text-muted-foreground">Not measured</dd>
          ) : (
            <>
              <dd
                data-numeric
                className="font-mono text-meta font-medium text-foreground"
              >
                {value.toFixed(0)}%
              </dd>
              <div
                aria-hidden
                className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-surface-sunken"
              >
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                />
              </div>
            </>
          )}
        </div>
      ))}
    </dl>
  );
}

/** The headline percentage.
 *
 * Deliberately not colour-coded by strength: an earlier version rendered every match in
 * `--success`, so a 21% match arrived in the same affirmative green as a 94% one. The
 * number carries its own magnitude.
 */
export function MatchScore({
  value,
  className,
}: {
  value: number | null;
  className?: string;
}) {
  return (
    <div className={cn("text-right", className)}>
      <p className="text-meta text-muted-foreground">Match</p>
      {value === null ? (
        <p className="text-meta text-muted-foreground">Not measured</p>
      ) : (
        <p
          data-numeric
          className="font-mono text-section font-medium text-foreground"
        >
          {value.toFixed(0)}%
        </p>
      )}
    </div>
  );
}
