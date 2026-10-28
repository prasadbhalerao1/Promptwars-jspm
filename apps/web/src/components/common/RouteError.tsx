"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Body shared by every route-group `error.tsx`.
 *
 * A group-level boundary catches the failure below the workspace layout, so the
 * sidebar and header survive and the user can navigate somewhere else instead of
 * being dropped onto a bare full-page error. Same reasoning as the root boundary
 * about not printing `error.message`: see `app/error.tsx`. */
export function RouteError({
  error,
  reset,
  area,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  /** What failed, in the user's words — "The evaluation queue", "This job". */
  area: string;
}) {
  useEffect(() => {
    console.error(`Unhandled error in ${area}:`, error);
  }, [error, area]);

  return (
    <div role="alert" className="rounded-xl p-8 text-center shadow-flat">
      <span className="mx-auto flex size-10 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle aria-hidden className="size-5 text-destructive" />
      </span>
      <h2 className="mt-4 text-section font-semibold text-foreground">
        {area} couldn&apos;t be loaded
      </h2>
      <p className="mx-auto mt-2 max-w-reading text-body leading-relaxed text-muted-foreground">
        Nothing was changed. Retrying is safe.
      </p>
      {error.digest && (
        <p className="mt-3 font-mono text-meta text-muted-foreground">
          Reference: {error.digest}
        </p>
      )}
      <Button className="mt-6" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
