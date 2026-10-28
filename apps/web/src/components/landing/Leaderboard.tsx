"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

/** A live hackathon leaderboard, with the contribution evidence underneath it.
 *
 * The point this makes is the differentiator: the leaderboard is not the end of the
 * event. Every row already carries per-member commit, PR and issue evidence, which is
 * what carries forward onto a talent profile once the event closes.
 *
 * Rows reorder on `layout` rather than on a re-render, so the ranking visibly settles.
 * That is the one moment on the page where a list animating is doing argument rather
 * than decoration.
 */

type Team = {
  name: string;
  project: string;
  score: number;
  members: readonly { name: string; commits: number; prs: number; issues: number }[];
};

/** Two orderings of the same teams. Scoring is still running in the first, so the
 * leaderboard settles into the second — the reorder is the demo. */
const PROVISIONAL: readonly Team[] = [
  {
    name: "Northwind",
    project: "Realtime incident triage",
    score: 88.2,
    members: [
      { name: "R. Okafor", commits: 142, prs: 18, issues: 24 },
      { name: "J. Lindqvist", commits: 96, prs: 11, issues: 15 },
    ],
  },
  {
    name: "Ledgerline",
    project: "Provenance for model outputs",
    score: 91.6,
    members: [
      { name: "A. Chen", commits: 208, prs: 27, issues: 31 },
      { name: "M. Duarte", commits: 118, prs: 14, issues: 19 },
    ],
  },
  {
    name: "Halfstack",
    project: "Offline-first field survey app",
    score: 84.9,
    members: [
      { name: "S. Varga", commits: 77, prs: 9, issues: 12 },
      { name: "T. Ibrahim", commits: 64, prs: 7, issues: 10 },
    ],
  },
] as const;

const FINAL = [1, 0, 2] as const;

const CYCLE = 5200;

export function Leaderboard() {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setOnScreen(true);
        observer.disconnect();
      },
      { threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const animating = onScreen && !reduced;

  useEffect(() => {
    if (!animating) {
      return;
    }
    // Settles shortly after entry, then re-runs so a visitor who scrolls back still sees
    // the reorder rather than a list that has already finished moving.
    const first = setTimeout(() => setSettled(true), 1400);
    const loop = setInterval(() => {
      setSettled((s) => !s);
    }, CYCLE);
    return () => {
      clearTimeout(first);
      clearInterval(loop);
    };
  }, [animating]);

  // With motion off the final standings are what matters, so that is what renders.
  const order = animating && !settled ? [0, 1, 2] : FINAL;
  const scoring = animating && !settled;

  return (
    <div ref={ref}>
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
          Leaderboard
        </p>
        <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
          <span
            aria-hidden
            className={
              scoring
                ? "size-1.5 animate-pulse rounded-full bg-primary"
                : "size-1.5 rounded-full bg-success"
            }
          />
          {scoring ? "Scoring" : "Final standings"}
        </span>
      </div>

      <ol className="mt-4">
        {order.map((teamIndex, rank) => {
          const team = PROVISIONAL[teamIndex];
          return (
            <motion.li
              key={team.name}
              layout={animating}
              transition={{ type: "spring", stiffness: 280, damping: 30 }}
              className={cn(
                "border-t py-5",
                rank === 0 && !scoring ? "border-primary/40" : "border-border",
              )}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <div className="flex min-w-0 items-baseline gap-3">
                  <span
                    aria-hidden
                    className="font-mono text-meta text-muted-foreground"
                  >
                    {String(rank + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <p className="text-section font-medium text-foreground">
                      {team.name}
                    </p>
                    <p className="text-meta text-muted-foreground">{team.project}</p>
                  </div>
                </div>
                <p
                  data-numeric
                  className="font-mono text-section font-medium text-foreground"
                >
                  {team.score.toFixed(1)}
                </p>
              </div>

              {/* Per-member evidence: the reason the leaderboard is worth more than a
                  photograph once the event is over. */}
              {/* Member evidence as inline data rather than chips: the contribution
                  figures are the point, and boxing each name added a rectangle without
                  adding meaning. */}
              <ul className="mt-3 flex flex-wrap gap-x-8 gap-y-1.5">
                {team.members.map((m) => (
                  <li
                    key={m.name}
                    className="flex items-baseline gap-2.5"
                  >
                    <span className="truncate text-meta text-foreground">{m.name}</span>
                    <span className="shrink-0 font-mono text-meta text-muted-foreground">
                      <span data-numeric>{m.commits}</span>c ·{" "}
                      <span data-numeric>{m.prs}</span>pr ·{" "}
                      <span data-numeric>{m.issues}</span>i
                    </span>
                  </li>
                ))}
              </ul>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
