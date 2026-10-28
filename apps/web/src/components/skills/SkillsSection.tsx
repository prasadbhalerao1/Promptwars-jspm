"use client";

import { useMemo } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import type { GithubProjectSummary } from "@/lib/api";

// Static keyword -> category map. Matched against repo topics (explicit, candidate-set
// GitHub tags) and languages (byte-count aggregated). Deliberately conservative: only
// categorizes signals we actually have data for — no package.json/framework parsing,
// since the ingestion pipeline doesn't fetch repo file contents.
const CATEGORY_KEYWORDS: Record<string, string[]> = {
  Frontend: [
    "react",
    "reactjs",
    "nextjs",
    "next-js",
    "vue",
    "vuejs",
    "angular",
    "svelte",
    "tailwindcss",
    "html",
    "css",
  ],
  Backend: [
    "nodejs",
    "node",
    "express",
    "expressjs",
    "fastapi",
    "django",
    "flask",
    "spring",
    "springboot",
    "graphql",
    "rest-api",
  ],
  Languages: [
    "typescript",
    "javascript",
    "python",
    "java",
    "c++",
    "c",
    "go",
    "golang",
    "rust",
    "ruby",
    "php",
    "kotlin",
    "swift",
    "c#",
  ],
  Databases: [
    "mongodb",
    "postgresql",
    "postgres",
    "mysql",
    "sqlite",
    "redis",
    "firebase",
    "supabase",
    "prisma",
  ],
  DevOps: [
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "terraform",
    "ci-cd",
    "github-actions",
    "devops",
  ],
};

function categorize(
  projects: GithubProjectSummary[],
): Record<string, Set<string>> {
  const categories: Record<string, Set<string>> = {
    Frontend: new Set(),
    Backend: new Set(),
    Languages: new Set(),
    Databases: new Set(),
    DevOps: new Set(),
  };

  const signals = new Set<string>();
  for (const project of projects) {
    for (const topic of project.topics ?? []) signals.add(topic.toLowerCase());
    for (const lang of Object.keys(project.languages ?? {}))
      signals.add(lang.toLowerCase());
  }

  for (const signal of signals) {
    for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
      if (keywords.includes(signal)) categories[category].add(signal);
    }
  }

  return categories;
}

export function SkillsSection({
  projects,
}: {
  projects: GithubProjectSummary[];
}) {
  const categories = useMemo(() => categorize(projects), [projects]);
  const hasAny = Object.values(categories).some((set) => set.size > 0);

  if (!hasAny) {
    return (
      <EmptyState
        title="No skills inferred yet"
        description="Skills are derived from repository topics and languages. Adding topics to your GitHub repos populates this section."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {Object.entries(categories)
        .filter(([, set]) => set.size > 0)
        .map(([category, set]) => (
          <div
            key={category}
            className="p-3.5 rounded-xl border border-border bg-card/40 hover:border-border/80 transition-colors"
          >
            <p className="mb-3 text-meta font-medium text-muted-foreground">
              {category}
            </p>
            <div className="flex flex-wrap gap-2">
              {[...set].map((skill) => (
                <Badge
                  key={skill}
                  variant="secondary"
                  className="border border-border bg-card text-foreground hover:border-border hover:text-foreground transition-all text-xs font-semibold px-2.5 py-1 capitalize"
                >
                  {skill}
                </Badge>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
