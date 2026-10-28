"use client";

import {
  Award,
  Flame,
  GitPullRequest,
  Globe2,
  Languages,
  Star,
} from "lucide-react";
import { useMemo } from "react";

import { AchievementCard } from "@/components/achievements/AchievementCard";
import type {
  GithubProjectSummary,
  GithubStats,
  GithubSummary,
} from "@/lib/api";

const TIER_CLASSNAMES = [
  "border-warning/20 bg-warning/10 text-warning",
  "border-border bg-card text-foreground",
  "border-warning/20 bg-warning/10 text-warning",
  "border-primary bg-primary/10 text-primary",
];
const TIER_LABELS = ["Bronze", "Silver", "Gold", "Platinum"];
// Module-scope (evaluated once at import time, not per render) — react-hooks/purity
// flags `Date.now()` reached from anywhere inside a component's render, even memoized.
const NOW_MS = Date.now();

function tierIndex(value: number, thresholds: number[]): number {
  let idx = -1;
  for (const t of thresholds) {
    if (value >= t) idx++;
  }
  return idx;
}

interface AchievementsGridProps {
  githubStats: GithubStats;
  githubSummary: GithubSummary;
  projects: GithubProjectSummary[];
}

/** Real-data-derived rank badges — tier thresholds adapted from common GitHub-analytics
 * conventions (star/commit/PR count bands), applied only to numbers we actually fetch. */
export function AchievementsGrid({
  githubStats,
  githubSummary,
  projects,
}: AchievementsGridProps) {
  const languageCount = useMemo(() => {
    const langs = new Set<string>();
    for (const p of projects)
      for (const lang of Object.keys(p.languages ?? {})) langs.add(lang);
    return langs.size;
  }, [projects]);

  const accountAgeYears = useMemo(() => {
    if (!githubStats.account_created_at) return 0;
    return (
      (NOW_MS - new Date(githubStats.account_created_at).getTime()) /
      (365 * 86_400_000)
    );
  }, [githubStats.account_created_at]);

  const starsTier = tierIndex(githubSummary.total_stars, [10, 100, 500, 1000]);
  const commitsTier = tierIndex(
    githubSummary.total_commits,
    [100, 500, 1000, 5000],
  );
  const prsTier = tierIndex(githubSummary.total_prs, [10, 50, 100, 500]);
  const followersTier = tierIndex(githubStats.followers, [10, 50, 100, 500]);

  const achievements = [
    {
      icon: Star,
      title: "Starred Developer",
      description:
        starsTier >= 0
          ? `${TIER_LABELS[starsTier]} tier - ${githubSummary.total_stars} stars`
          : "Earn 10+ stars to unlock",
      earned: starsTier >= 0,
      tier: starsTier,
    },
    {
      icon: GitPullRequest,
      title: "Commit Machine",
      description:
        commitsTier >= 0
          ? `${TIER_LABELS[commitsTier]} tier - ${githubSummary.total_commits} commits`
          : "Reach 100+ commits to unlock",
      earned: commitsTier >= 0,
      tier: commitsTier,
    },
    {
      icon: GitPullRequest,
      title: "Pull Request Pro",
      description:
        prsTier >= 0
          ? `${TIER_LABELS[prsTier]} tier - ${githubSummary.total_prs} PRs`
          : "Open 10+ PRs to unlock",
      earned: prsTier >= 0,
      tier: prsTier,
    },
    {
      icon: Globe2,
      title: "Open Source Contributor",
      description:
        githubSummary.external_contributions > 0
          ? `${githubSummary.external_contributions} merged PRs to others' repos`
          : "Get a PR merged into a repo you don't own",
      earned: githubSummary.external_contributions > 0,
      tier: 2,
    },
    {
      icon: Flame,
      title: "Consistent Committer",
      description:
        githubStats.longest_streak >= 30
          ? `${githubStats.longest_streak}-day longest streak`
          : "Reach a 30-day contribution streak",
      earned: githubStats.longest_streak >= 30,
      tier:
        githubStats.longest_streak >= 100
          ? 3
          : githubStats.longest_streak >= 60
            ? 2
            : 1,
    },
    {
      icon: Languages,
      title: "Polyglot Developer",
      description:
        languageCount >= 5
          ? `${languageCount} languages across your repos`
          : "Use 5+ languages across your repos",
      earned: languageCount >= 5,
      tier: languageCount >= 10 ? 3 : languageCount >= 7 ? 2 : 1,
    },
    {
      icon: Award,
      title: "Early Adopter",
      description:
        accountAgeYears >= 5
          ? `On GitHub for ${Math.floor(accountAgeYears)}+ years`
          : "5+ year GitHub account",
      earned: accountAgeYears >= 5,
      tier: 2,
    },
    {
      icon: Star,
      title: "Community Favorite",
      description:
        followersTier >= 0
          ? `${TIER_LABELS[followersTier]} tier - ${githubStats.followers} followers`
          : "Reach 10+ followers to unlock",
      earned: followersTier >= 0,
      tier: followersTier,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {achievements.map((a, i) => (
        <AchievementCard
          key={a.title}
          icon={a.icon}
          title={a.title}
          description={a.description}
          earned={a.earned}
          tierClassName={TIER_CLASSNAMES[Math.max(0, Math.min(3, a.tier))]}
          index={i}
        />
      ))}
    </div>
  );
}
