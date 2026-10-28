import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  /** What this list would contain. Not "No data found" — name the thing. */
  title: string;
  /** Why it's empty and what fills it. */
  description?: string;
  icon?: LucideIcon;
  /** The action that resolves the emptiness, when one exists. */
  action?: React.ReactNode;
  className?: string;
}

/** Empty state for any list or panel.
 *
 * This was previously a one-line stub rendering a grey `<p>`, which is why pages
 * hand-rolled strings like "No submissions yet." inline instead of adopting it. An
 * empty state should explain what belongs here and offer the next step. */
export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg bg-muted/40 px-6 py-10 text-center",
        className,
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-full bg-background shadow-flat">
        <Icon aria-hidden className="size-4 text-muted-foreground" />
      </span>
      <div className="space-y-1">
        <p className="text-body font-medium text-foreground">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-meta text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
