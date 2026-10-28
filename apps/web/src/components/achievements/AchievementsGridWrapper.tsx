"use client";

import { Section } from "@/components/common/Section";
import { AchievementsGrid } from "@/components/achievements/AchievementsGrid";
import type {
  GithubProjectSummary,
  GithubStats,
  GithubSummary,
} from "@/lib/api";

interface AchievementsGridWrapperProps {
  githubStats: GithubStats;
  githubSummary: GithubSummary;
  projects: GithubProjectSummary[];
}

export function AchievementsGridWrapper({
  githubStats,
  githubSummary,
  projects,
}: AchievementsGridWrapperProps) {
  return (
    <Section title="Achievements">
      <AchievementsGrid
        githubStats={githubStats}
        githubSummary={githubSummary}
        projects={projects}
      />
    </Section>
  );
}
