"use client";

import { useMemo } from "react";
import { FolderGit2 } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { RepositoryCard } from "@/components/repositories/RepositoryCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { GithubProjectSummary } from "@/lib/api";

export function RepositoryGrid({
  projects,
}: {
  projects: GithubProjectSummary[];
}) {
  const mostStarred = useMemo(
    () => [...projects].sort((a, b) => (b.stars ?? 0) - (a.stars ?? 0)),
    [projects],
  );
  const recentlyUpdated = useMemo(
    () =>
      [...projects].sort((a, b) => {
        if (!a.pushed_at) return 1;
        if (!b.pushed_at) return -1;
        return (
          new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime()
        );
      }),
    [projects],
  );

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={FolderGit2}
        title="No repositories synced yet"
        description="Connect GitHub to pull in your public repositories and their commit history."
      />
    );
  }

  return (
    <Tabs defaultValue="starred" className="w-full">
      <TabsList className="bg-muted border border-border/80 p-1 rounded-lg h-9">
        <TabsTrigger
          value="starred"
          className="text-meta font-medium font-mono text-muted-foreground data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-flat rounded-md px-3"
        >
          Most Starred
        </TabsTrigger>
        <TabsTrigger
          value="recent"
          className="text-meta font-medium font-mono text-muted-foreground data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-flat rounded-md px-3"
        >
          Recently Updated
        </TabsTrigger>
      </TabsList>
      <TabsContent
        value="starred"
        className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 focus-visible:outline-none"
      >
        {mostStarred.slice(0, 8).map((project, i) => (
          <RepositoryCard
            key={project.repo_full_name}
            project={project}
            index={i}
          />
        ))}
      </TabsContent>
      <TabsContent
        value="recent"
        className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 focus-visible:outline-none"
      >
        {recentlyUpdated.slice(0, 8).map((project, i) => (
          <RepositoryCard
            key={project.repo_full_name}
            project={project}
            index={i}
          />
        ))}
      </TabsContent>
    </Tabs>
  );
}
