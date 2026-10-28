"use client";

import { Suspense } from "react";

import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

/** Deliberately outside every route group.
 *
 * The five workspace layouts redirect here whenever `me.onboarding_required` is true,
 * so putting this route inside one of them would redirect to itself. It also has no
 * sidebar by design — there is nothing to navigate to until the profile exists.
 *
 * The wizard reads `?github=` via useSearchParams to resume after an OAuth round trip,
 * which requires a Suspense boundary above it.
 */
export default function OnboardingPage() {
  return (
    <div className="mx-auto w-full max-w-2xl p-8">
      <Suspense
        fallback={
          <div className="space-y-4">
            <div className="h-1.5 w-full animate-pulse rounded-full bg-muted" />
            <div className="h-64 animate-pulse rounded-xl bg-muted" />
          </div>
        }
      >
        <OnboardingWizard />
      </Suspense>
    </div>
  );
}
