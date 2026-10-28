import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

/** Composite loading placeholders built on the shadcn `Skeleton` primitive.
 *
 * Size these to match the content they stand in for — a skeleton whose dimensions
 * differ from the real element just relocates the layout shift instead of removing it.
 */

/** Page heading + subtitle. Matches the `h1` + `p` pair that opens nearly every page. */
export function PageHeaderSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="h-4 w-80 opacity-70" />
    </div>
  );
}

/** Card-shaped placeholder. Renders the real card's border and surface so only the
 * inner content pops in when data lands. */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("rounded-lg border border-border bg-card", className)}
    />
  );
}

/** Generic page fallback: header plus a couple of cards. Used by route-level
 * loading.tsx files where the exact shape varies between sibling routes. */
export function PageSkeleton() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <CardSkeleton className="h-40" />
        <CardSkeleton className="h-40" />
      </div>
      <CardSkeleton className="h-64" />
    </div>
  );
}

/** Vertical list of rows — job lists, application lists, queues, audit logs. */
export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <CardSkeleton key={i} className="h-20" />
      ))}
    </div>
  );
}
