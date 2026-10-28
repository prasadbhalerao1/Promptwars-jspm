import { PageHeaderSkeleton, ListSkeleton } from "@/components/common/Skeleton";

// List-heavy route: header plus rows, matching the real page's shape so the layout
// doesn't shift when data lands.
export default function Loading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <ListSkeleton rows={6} />
    </div>
  );
}
