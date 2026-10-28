"use client";

import Link from "next/link";
import { Check, ChevronRight } from "lucide-react";

import type { CandidateProfileResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface CompletenessItem {
  label: string;
  done: boolean;
  href: string;
}

/** Derives the checklist from the profile. Mirrors the onboarding wizard's required
 * fields, so anything a candidate skipped there (GitHub in particular, which is
 * skippable by design) keeps surfacing here until it's done.
 *
 * College/degree are not top-level columns — `PATCH /candidates/me` folds them into
 * the first entry of the `education` JSONB array as `institution`/`degree`
 * (services/api/modules/candidates/router.py), so they're read back the same way. */
export function buildChecklist(
  profile: CandidateProfileResponse | null,
): CompletenessItem[] {
  const education = (profile?.education?.[0] ?? {}) as Record<string, unknown>;
  const hasEducation =
    Boolean(education.institution) && Boolean(education.degree);

  return [
    {
      label: "Add your headline",
      done: Boolean(profile?.headline),
      href: "/profile/edit",
    },
    {
      label: "Set your location",
      done: Boolean(profile?.location),
      href: "/profile/edit",
    },
    {
      label: "Add college & degree",
      done: hasEducation,
      href: "/profile/edit",
    },
    {
      label: "Connect GitHub",
      done: Boolean(profile?.github_username),
      href: "/profile/edit",
    },
    {
      label: "Connect LeetCode",
      done: Boolean(profile?.leetcode_username),
      href: "/profile/edit",
    },
  ];
}

/** Progress meter shown on the candidate hub. Hidden entirely once everything is
 * done — a permanent "100%" badge is just noise after the first week. */
export function ProfileCompleteness({
  profile,
}: {
  profile: CandidateProfileResponse | null;
}) {
  const items = buildChecklist(profile);
  const completed = items.filter((i) => i.done).length;
  const pct = Math.round((completed / items.length) * 100);

  if (completed === items.length) return null;

  const nextUp = items.find((i) => !i.done);

  return (
    <div className="rounded-lg bg-warning/10 p-5 shadow-flat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-semibold text-foreground">
            Complete your profile
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Recruiters rank verified profiles higher -{" "}
            {items.length - completed} step
            {items.length - completed === 1 ? "" : "s"} left.
          </p>
        </div>
        {nextUp && (
          <Button size="sm" render={<Link href={nextUp.href} />}>
            {nextUp.label}
            <ChevronRight className="ml-1 size-4" />
          </Button>
        )}
      </div>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-warning/20">
        <div
          className="h-full rounded-full bg-warning transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {items.map((item) => (
          <li
            key={item.label}
            className={
              item.done
                ? "flex items-center gap-1.5 text-xs text-muted-foreground line-through"
                : "flex items-center gap-1.5 text-xs font-medium text-foreground"
            }
          >
            <span
              className={
                item.done
                  ? "flex size-4 items-center justify-center rounded-full bg-success text-success-foreground"
                  : "size-4 rounded-full border border-dashed border-border"
              }
            >
              {item.done && <Check className="size-2.5" strokeWidth={3} />}
            </span>
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
