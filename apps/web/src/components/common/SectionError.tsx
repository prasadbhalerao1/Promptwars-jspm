import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Scoped failure banner for one independently-fetched section — sibling sections keep
 * rendering even when this one failed (see useAsyncResource).
 *
 * Errors must always offer a way forward, so the retry is part of the component rather
 * than something each caller remembers to add. */
export function SectionError({
  message,
  onRetry,
  retrying,
  className,
}: {
  message: string;
  onRetry: () => void;
  retrying: boolean;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-3 rounded-lg bg-destructive/10 px-4 py-3 text-body text-destructive shadow-flat sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <span className="flex items-start gap-2">
        <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
        <span>{message}</span>
      </span>
      <Button size="sm" variant="outline" onClick={onRetry} disabled={retrying}>
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </div>
  );
}
