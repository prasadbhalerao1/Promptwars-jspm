"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Root error boundary.
 *
 * Deliberately does NOT print `error.message`. In production Next.js replaces the
 * message with a generic string and exposes `digest` instead, so the old raw-message
 * panel showed developers nothing useful and end users an unexplained stack fragment.
 * The digest is what actually correlates to a server log, so that is what is shown. */
export default function GlobalErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled UI error:", error);
  }, [error]);

  return (
    <div className="flex flex-1 items-center justify-center px-6 py-24">
      <div role="alert" className="w-full max-w-reading text-center">
        <span className="mx-auto flex size-10 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle aria-hidden className="size-5 text-destructive" />
        </span>
        <h1 className="mt-4 text-title font-semibold text-foreground">
          Something went wrong
        </h1>
        <p className="mt-2 text-body leading-relaxed text-muted-foreground">
          This page failed to render. Your data has not been affected - retrying
          is safe.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-meta text-muted-foreground">
            Reference: {error.digest}
          </p>
        )}
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button onClick={reset}>Try again</Button>
          <Button variant="outline" render={<Link href="/home" />}>
            Back to your workspace
          </Button>
        </div>
      </div>
    </div>
  );
}
