import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AttentionCardProps {
  /** How many things are waiting. `0` renders the resolved state rather than a card
   * shouting about nothing. */
  count: number;
  /** Singular noun — "submission", "flag". Pluralized automatically. */
  noun: string;
  /** What the user does about it: "awaiting your score". */
  verb: string;
  href: string;
  actionLabel: string;
  icon?: LucideIcon;
  /** Shown instead of the count when there is nothing to do. */
  clearedLabel?: string;
  className?: string;
}

/** The lead element of a role hub: work that is waiting on this person.
 *
 * Hubs previously opened with an undifferentiated grid of feature cards, which answers
 * "what can I do?" but never "what needs me now?". This answers the second question,
 * which is the one someone opening the app actually has. */
export function AttentionCard({
  count,
  noun,
  verb,
  href,
  actionLabel,
  icon: Icon,
  clearedLabel = "You're all caught up",
  className,
}: AttentionCardProps) {
  const cleared = count === 0;

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg bg-card px-5 py-4 shadow-flat sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        {Icon ? (
          <span
            className={cn(
              "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md",
              cleared
                ? "bg-muted text-muted-foreground"
                : "bg-primary/10 text-primary",
            )}
          >
            <Icon aria-hidden className="size-4" />
          </span>
        ) : null}
        <div className="min-w-0">
          {cleared ? (
            <p className="text-body font-medium text-foreground">
              {clearedLabel}
            </p>
          ) : (
            <p className="text-body font-medium text-foreground">
              <span data-numeric className="tabular-nums">
                {count}
              </span>{" "}
              {count === 1 ? noun : `${noun}s`} {verb}
            </p>
          )}
        </div>
      </div>
      <Button
        size="sm"
        variant={cleared ? "outline" : "default"}
        render={<Link href={href} />}
        className="shrink-0"
      >
        {actionLabel}
      </Button>
    </div>
  );
}
