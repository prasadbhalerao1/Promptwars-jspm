"use client";

import { motion } from "framer-motion";
import { GitFork, Star } from "lucide-react";

import type { GithubProjectSummary } from "@/lib/api";

function timeAgo(iso: string | null): string | null {
  if (!iso) return null;
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export function RepositoryCard({
  project,
  index = 0,
}: {
  project: GithubProjectSummary;
  index?: number;
}) {
  const topLanguage = project.languages
    ? Object.keys(project.languages)[0]
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.2 }}
      whileHover={{ y: -2 }}
      className="flex flex-col justify-between rounded-xl border border-border bg-card p-4 transition-all duration-300 hover:border-border hover:bg-card/20 hover:shadow-flat hover:"
    >
      <div>
        <p className="truncate text-sm font-bold text-foreground font-heading tracking-tight">
          {project.repo_full_name}
        </p>
        {project.description && (
          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground font-sans">
            {project.description}
          </p>
        )}
        {project.topics && project.topics.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {project.topics.slice(0, 4).map((topic) => (
              <span
                key={topic}
                className="rounded-md bg-card border border-border px-2 py-0.5 text-meta font-medium text-muted-foreground"
              >
                {topic}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="mt-4 flex items-center gap-4 text-meta font-medium text-muted-foreground select-none">
        {topLanguage && (
          <span className="flex items-center gap-1 text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            {topLanguage}
          </span>
        )}
        <span className="flex items-center gap-1 hover:text-foreground transition-colors">
          <Star className="h-3.5 w-3.5 text-warning" /> {project.stars ?? 0}
        </span>
        <span className="flex items-center gap-1 hover:text-foreground transition-colors">
          <GitFork className="h-3.5 w-3.5 text-muted-foreground" /> {project.forks ?? 0}
        </span>
        {timeAgo(project.pushed_at) && (
          <span className="ml-auto text-muted-foreground font-medium">
            {timeAgo(project.pushed_at)}
          </span>
        )}
      </div>
    </motion.div>
  );
}
