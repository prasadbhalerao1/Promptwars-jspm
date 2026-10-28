"use client";

import {
  CalendarDays,
  Flame,
  FolderGit2,
  GitCommit,
  GitPullRequest,
  Star,
  Trophy,
  Zap,
} from "lucide-react";

import { StatCard } from "@/components/stats/StatCard";
import type { GithubStats, GithubSummary } from "@/lib/api";

export function StatsGrid({
  stats,
  summary,
}: {
  stats: GithubStats;
  summary?: GithubSummary | null;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 w-full">
      <StatCard
        label="Contributions"
        value={stats.total_contributions}
        icon={Zap}
      />
      <StatCard
        label="Total Commits"
        value={summary?.total_commits ?? stats.total_contributions}
        icon={GitCommit}
      />
      <StatCard
        label="Current Streak"
        value={`${stats.current_streak}d`}
        icon={Flame}
        iconClassName="text-amber-500"
      />
      <StatCard
        label="Stars Earned"
        value={summary?.total_stars ?? 0}
        icon={Star}
        iconClassName="text-amber-500"
      />
      <StatCard
        label="Pull Requests"
        value={summary?.total_prs ?? 0}
        icon={GitPullRequest}
        iconClassName="text-emerald-500"
      />
      <StatCard
        label="Public Repos"
        value={stats.public_repos || summary?.owned_repo_count || 0}
        icon={FolderGit2}
      />
    </div>
  );
}
