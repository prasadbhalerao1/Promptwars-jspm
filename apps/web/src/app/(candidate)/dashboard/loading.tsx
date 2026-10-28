import { PageSkeleton } from "@/components/common/Skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-workspace px-4 py-6 md:px-8 md:py-8">
      <PageSkeleton />
    </div>
  );
}
