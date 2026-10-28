import { PageSkeleton } from "@/components/common/Skeleton";

// Route-level Suspense fallback. Without this, Next holds the *previous* page on screen
// for the whole duration of a navigation, so switching routes felt like a freeze rather
// than a transition. The workspace sidebar comes from the layout and stays mounted; only
// this main-content area swaps.
export default function Loading() {
  return <PageSkeleton />;
}
