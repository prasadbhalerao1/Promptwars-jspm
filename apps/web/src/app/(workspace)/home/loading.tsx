import { PageHeaderSkeleton, CardSkeleton } from "@/components/common/Skeleton";

export default function Loading() {
  // Width and padding must match WorkspaceShell's content container
  // (max-w-workspace, px-4 py-8 md:px-8) - a mismatched skeleton shifts the whole page
  // sideways by the difference the moment the real content lands.
  return (
    <div className="mx-auto w-full max-w-workspace space-y-8 px-4 py-8 md:px-8">
      <PageHeaderSkeleton />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <CardSkeleton key={i} className="h-36" />
        ))}
      </div>
    </div>
  );
}
