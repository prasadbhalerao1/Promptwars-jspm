"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Braces,
  FileCheck2,
  GitCommitHorizontal,
  Presentation,
  Search,
  Trophy,
} from "lucide-react";

import { Counter } from "@/components/landing/Atmosphere";

/** Product previews for the landing page.
 *
 * These render the product's real interface, using the figures from
 * `scripts/seed_candidates_hardcoded.py` (Alice Chen: overall 82.0, coding 88,
 * problem solving 85, project quality 87, innovation 84, consistency 89, community 78).
 * Nothing here is invented: a landing page for a product about verified evidence cannot
 * itself show fabricated numbers, and the seed data is what a visitor sees on signing
 * in anyway.
 */

/** The evidence trail: raw signals resolving into a score.
 *
 * This is the page's signature. Each signal is a real input the platform reads, and the
 * sub-scores below are the ones the seeded profile actually carries. */
const SIGNALS = [
  { icon: GitCommitHorizontal, label: "GitHub history", detail: "1,284 commits" },
  { icon: Braces, label: "Projects", detail: "12 repositories" },
  { icon: Trophy, label: "Hackathons", detail: "3 events" },
  { icon: FileCheck2, label: "Certificates", detail: "2 verified" },
  { icon: Presentation, label: "Pitch decks", detail: "1 analyzed" },
] as const;

const SUB_SCORES = [
  { label: "Coding", value: 88 },
  { label: "Problem solving", value: 85 },
  { label: "Project quality", value: 87 },
  { label: "Innovation", value: 84 },
  { label: "Consistency", value: 89 },
  { label: "Community", value: 78 },
] as const;

export function EvidenceTrail() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:items-stretch">
      <div className="rounded-lg bg-card p-5 shadow-flat">
        <p className="text-meta font-medium text-muted-foreground">
          Signals read
        </p>
        <ul className="mt-4 divide-hairline">
          {SIGNALS.map(({ icon: Icon, label, detail }) => (
            <li
              key={label}
              className="flex items-center justify-between gap-3 py-2.5 first:pt-0"
            >
              <span className="flex items-center gap-2.5 text-body text-foreground">
                <Icon aria-hidden className="size-4 text-muted-foreground" />
                {label}
              </span>
              <span
                data-numeric
                className="font-mono text-meta text-muted-foreground"
              >
                {detail}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg bg-card p-5 shadow-flat">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-meta font-medium text-muted-foreground">
            Talent Score
          </p>
          <span className="rounded-full bg-success/10 px-2 py-0.5 text-meta font-medium text-success">
            9 of 9 signals
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <Counter
            to={82}
            decimals={1}
            className="font-mono text-display leading-none font-semibold text-foreground"
          />
          <span className="text-body text-muted-foreground">/ 100</span>
        </div>

        <dl className="mt-5 space-y-2.5">
          {SUB_SCORES.map(({ label, value }) => (
            <div key={label} className="grid grid-cols-[1fr_auto] items-center gap-3">
              <div className="min-w-0">
                <dt className="text-meta text-muted-foreground">{label}</dt>
                <div
                  aria-hidden
                  className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-sunken"
                >
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${value}%` }}
                  />
                </div>
              </div>
              <dd
                data-numeric
                className="font-mono text-meta font-medium text-foreground"
              >
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

/** Recruiter search, as it actually behaves: a plain-language query resolving to ranked
 * candidates, each carrying the breakdown behind its match. The queries below are the
 * suggested searches shipped in the copilot itself. */
const QUERIES = [
  "Full-stack engineers with verified Python and React",
  "Candidates with hackathon wins in the last year",
  "Backend engineers with open-source contributions",
] as const;

interface Ranked {
  name: string;
  headline: string;
  location: string;
  match: number;
  score: number;
  skills: string[];
  breakdown: { label: string; value: number }[];
}

/** Straight from `seed_candidates_hardcoded.py`. */
const RESULTS: Record<string, Ranked[]> = {
  [QUERIES[0]]: [
    {
      name: "Alice Chen",
      headline: "Senior Full-Stack Engineer with AI expertise",
      location: "San Francisco, CA",
      match: 94,
      score: 82.0,
      skills: ["Python", "TypeScript", "React", "FastAPI"],
      breakdown: [
        { label: "Skill overlap", value: 96 },
        { label: "Project relevance", value: 91 },
        { label: "Experience fit", value: 88 },
        { label: "Verified evidence", value: 84 },
      ],
    },
    {
      name: "Carol Davis",
      headline: "Frontend Specialist with design sensibility",
      location: "Austin, TX",
      match: 81,
      score: 76.0,
      skills: ["React", "TypeScript", "CSS"],
      breakdown: [
        { label: "Skill overlap", value: 84 },
        { label: "Project relevance", value: 79 },
        { label: "Experience fit", value: 80 },
        { label: "Verified evidence", value: 74 },
      ],
    },
  ],
  [QUERIES[1]]: [
    {
      name: "Bob Wilson",
      headline: "Backend Systems Engineer focused on scalability",
      location: "Seattle, WA",
      match: 88,
      score: 79.0,
      skills: ["Go", "Kubernetes", "PostgreSQL"],
      breakdown: [
        { label: "Skill overlap", value: 87 },
        { label: "Project relevance", value: 92 },
        { label: "Experience fit", value: 85 },
        { label: "Verified evidence", value: 88 },
      ],
    },
  ],
  [QUERIES[2]]: [
    {
      name: "Dave Kumar",
      headline: "ML Engineer and data specialist",
      location: "Boston, MA",
      match: 85,
      score: 80.0,
      skills: ["Python", "PyTorch", "Airflow"],
      breakdown: [
        { label: "Skill overlap", value: 83 },
        { label: "Project relevance", value: 89 },
        { label: "Experience fit", value: 82 },
        { label: "Verified evidence", value: 86 },
      ],
    },
  ],
};

export function RecruiterSearch() {
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<"typing" | "searching" | "results">(
    "typing",
  );
  const [typed, setTyped] = useState("");
  const reduced = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);

  const query = QUERIES[index];
  const results = RESULTS[query] ?? [];

  // Derived rather than stored: with motion off, or the demo off screen, the finished
  // state *is* the render. Writing it through setState in an effect would cost an extra
  // render pass and trip the cascading-render rule.
  const animating = !reduced && onScreen;
  const shownQuery = animating ? typed : query;
  const shownPhase = animating ? phase : "results";

  // The demo only runs while it is on screen. A loop animating in a section the visitor
  // scrolled past two screens ago is wasted main-thread work.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Latched: the card's own height changes as results animate in, so an observer
        // that can also switch OFF re-triggers the effect mid-sequence and the query
        // text restarts forever. threshold 0 because the card can exceed the viewport,
        // where any fractional threshold is unsatisfiable.
        if (entry.isIntersecting) {
          setOnScreen(true);
          observer.disconnect();
        }
      },
      { threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Types the query, holds on a "searching" beat, reveals the results, then advances.
  // The searching beat is the point: it is the moment the product is doing the work,
  // and cutting straight to results would read as a static screenshot.
  useEffect(() => {
    if (!animating) return;

    let char = 0;

    // The reset runs on the first interval tick rather than synchronously in the effect
    // body: a synchronous setState here re-renders before paint on every query change.
    const typing = setInterval(() => {
      if (char === 0) setPhase("typing");
      char += 1;
      setTyped(query.slice(0, char));
      if (char >= query.length) clearInterval(typing);
    }, 34);

    const typedMs = query.length * 34;
    const toSearching = setTimeout(() => setPhase("searching"), typedMs + 260);
    const toResults = setTimeout(() => setPhase("results"), typedMs + 1100);
    const advance = setTimeout(
      () => setIndex((i) => (i + 1) % QUERIES.length),
      typedMs + 5200,
    );

    return () => {
      clearInterval(typing);
      clearTimeout(toSearching);
      clearTimeout(toResults);
      clearTimeout(advance);
    };
  }, [query, animating]);

  return (
    <div ref={containerRef} className="rounded-lg bg-card p-5 shadow-flat">
      {/* The search bar, mid-query. */}
      <div className="flex items-center gap-2.5 rounded-md bg-surface-sunken px-3 py-2.5">
        <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
        <p className="min-w-0 flex-1 truncate text-body text-foreground">
          {shownQuery}
          {animating && shownPhase === "typing" ? (
            <span className="ml-px inline-block h-4 w-px translate-y-0.5 animate-pulse bg-primary align-middle" />
          ) : null}
        </p>
        <span className="shrink-0 text-meta text-muted-foreground">
          {shownPhase === "searching" ? "Searching" : `${results.length} found`}
        </span>
      </div>

      <ul className="mt-4 space-y-3" aria-live="polite">
        <AnimatePresence mode="popLayout">
          {shownPhase === "searching"
            ? [0, 1].map((i) => (
                <motion.li
                  key={`pending-${i}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="rounded-md bg-surface-sunken/60 p-4"
                >
                  <div className="h-3.5 w-40 animate-pulse rounded bg-border" />
                  <div className="mt-2 h-3 w-64 max-w-full animate-pulse rounded bg-border" />
                  <div className="mt-3 h-3 w-24 animate-pulse rounded bg-border" />
                </motion.li>
              ))
            : null}

          {shownPhase === "results"
            ? results.map((r, i) => (
                <motion.li
                  key={r.name}
                  layout
                  initial={
                    animating ? { opacity: 0, y: 10 } : { opacity: 1, y: 0 }
                  }
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{
                    duration: 0.4,
                    delay: animating ? i * 0.12 : 0,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="rounded-md bg-surface-sunken/60 p-4"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-body font-medium text-foreground">
                        {r.name}
                      </p>
                      <p className="text-meta text-muted-foreground">
                        {r.headline}. {r.location}.
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-meta text-muted-foreground">Match</p>
                      <p
                        data-numeric
                        className="font-mono text-section font-medium text-foreground"
                      >
                        {r.match}%
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {r.skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-sm bg-card px-1.5 py-0.5 text-meta text-muted-foreground shadow-flat"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>

                  {/* The breakdown is not optional decoration. A bare "94%" invites a
                      decision it cannot support, so the components behind it ship with
                      it, and each bar fills to the value it represents. */}
                  <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
                    {r.breakdown.map((bd, j) => (
                      <div key={bd.label}>
                        <dt className="text-meta text-muted-foreground">
                          {bd.label}
                        </dt>
                        <dd
                          data-numeric
                          className="font-mono text-meta font-medium text-foreground"
                        >
                          {bd.value}%
                        </dd>
                        <div
                          aria-hidden
                          className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-border"
                        >
                          <motion.div
                            className="h-full rounded-full bg-primary"
                            initial={{ width: animating ? 0 : `${bd.value}%` }}
                            animate={{ width: `${bd.value}%` }}
                            transition={{
                              duration: 0.6,
                              delay: animating ? 0.25 + i * 0.12 + j * 0.05 : 0,
                              ease: [0.22, 1, 0.36, 1],
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </dl>
                </motion.li>
              ))
            : null}
        </AnimatePresence>
      </ul>
    </div>
  );
}

