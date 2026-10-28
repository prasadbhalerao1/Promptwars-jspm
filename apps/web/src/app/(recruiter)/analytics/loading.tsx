import { PageHeaderSkeleton, CardSkeleton } from "@/components/common/Skeleton";

// Analytics is three charts (hiring funnel, time-to-hire histogram, source breakdown),
// not a list — the placeholder mirrors that grid so nothing jumps when they render.
export default function Loading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <CardSkeleton className="h-72" />
        <CardSkeleton className="h-72" />
      </div>
      <CardSkeleton className="h-72" />
    </div>
  );
}
