import { PageHeaderSkeleton, CardSkeleton } from "@/components/common/Skeleton";

// The pipeline is a horizontal kanban (one column per application stage), so a vertical
// list placeholder would shift the whole page sideways when the board mounts.
export default function Loading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <CardSkeleton key={i} className="h-96" />
        ))}
      </div>
    </div>
  );
}
