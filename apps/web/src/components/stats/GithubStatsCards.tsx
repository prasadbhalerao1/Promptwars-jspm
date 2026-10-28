"use client";

import {
  AlertTriangle,
  FolderGit2,
  GitCommit,
  GitFork,
  GitPullRequest,
  Star,
} from "lucide-react";

import { StatCard } from "@/components/stats/StatCard";
import type { GithubSummary } from "@/lib/api";

export function GithubStatsCards({ summary }: { summary: GithubSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      <StatCard
        label="Stars"
        value={summary.total_stars}
        icon={Star}
        iconClassName="text-warning"
      />
      <StatCard
        label="Commits"
        value={summary.total_commits}
        icon={GitCommit}
        iconClassName="text-warning"
      />
      <StatCard
        label="Pull Requests"
        value={summary.total_prs}
        icon={GitPullRequest}
        iconClassName="text-success"
      />
      <StatCard
        label="Issues"
        value={summary.total_issues}
        icon={AlertTriangle}
        iconClassName="text-destructive"
      />
      <StatCard
        label="Forks"
        value={summary.total_forks}
        icon={GitFork}
        iconClassName="text-chart-1"
      />
      <StatCard
        label="Repositories"
        value={summary.owned_repo_count}
        icon={FolderGit2}
      />
    </div>
  );
}
