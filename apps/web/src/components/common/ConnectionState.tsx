"use client";

import { Loader2, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";

/** A failed `fetch()` rejects with a bare TypeError — "Failed to fetch" — which is
 * indistinguishable from an application error to the user but means something quite
 * different: the request never reached the server. In this app that is nearly always
 * the API still pre-warming its 1.3GB embedding model at boot (10-30s), not a fault.
 *
 * `res.ok === false` paths throw `GET /x failed: 500`-style messages instead, so the
 * absence of a status code is what separates the two. */
export function isConnectionError(message: string | null | undefined): boolean {
  if (!message) return false;
  return (
    /failed to fetch|networkerror|network request failed|load failed/i.test(
      message,
    ) && !/\b[45]\d\d\b/.test(message)
  );
}

/** Shown in place of a hard error while the server is unreachable. Frames the wait as
 * expected rather than broken, and retries on its own so a user who waits is never
 * required to click anything. */
export function ConnectionState({
  onRetry,
  retrying,
  attempts,
}: {
  onRetry: () => void;
  retrying: boolean;
  /** Drives the copy only — after several failed attempts this stops claiming the
   * server is "starting up" and admits it may not be running at all. */
  attempts: number;
}) {
  const persistent = attempts >= 4;

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card px-6 py-10 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-warning/10 text-warning">
        {persistent ? (
          <WifiOff className="size-5" />
        ) : (
          <Loader2 className="size-5 animate-spin" />
        )}
      </span>

      <div className="space-y-1">
        <p className="font-heading text-sm font-semibold text-foreground">
          {persistent
            ? "Still can't reach the server"
            : "Connecting to the server…"}
        </p>
        <p className="max-w-sm text-xs text-muted-foreground">
          {persistent
            ? "The API doesn't seem to be responding. Check that it's running, then try again."
            : "The server takes a few seconds to warm up after starting. This will clear on its own."}
        </p>
      </div>

      <Button size="sm" variant="outline" onClick={onRetry} disabled={retrying}>
        {retrying ? "Retrying…" : "Retry now"}
      </Button>
    </div>
  );
}
