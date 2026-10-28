import { Skeleton } from "@/components/ui/skeleton";

/** Placeholder matching KanbanBoard's 6-column layout — used instead of a plain
 * "Loading pipeline…" line so the page doesn't reflow once real data arrives. */
export function KanbanSkeleton() {
  return (
    <div
      className="grid grid-cols-1 md:grid-cols-6 gap-4"
      aria-busy="true"
      aria-label="Loading pipeline"
    >
      {Array.from({ length: 6 }).map((_, col) => (
        <div key={col} className="space-y-3">
          <Skeleton className="h-4 w-2/3" />
          {Array.from({ length: 2 }).map((_, card) => (
            <div key={card} className="rounded-md border p-3 space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
