"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Signature moment 01: a resume dismantled into the evidence underneath it.
 *
 * The product's entire thesis, shown rather than argued. Each resume claim is traced,
 * struck through, and replaced by the record that actually supports it - `React` becomes
 * 1,284 commits across 12 repositories. When every claim has been replaced, what is left
 * is not a document but a profile, and the score resolves.
 *
 * Deliberately not inside a bordered card: the previous hero put a dashboard in a box on
 * the right, which read as a screenshot beside a headline rather than as the product
 * doing something. Here the evidence occupies the space directly.
 *
 * Figures are the seeded profile's real ones (overall 82.4, sub-scores 88/85/87/84/89/78),
 * matching `scripts/seed_candidates_hardcoded.py` and `GET /candidates/me/score`.
 */

type Claim = {
  /** What the resume asserts. */
  claim: string;
  /** Where TRACE looked. */
  source: string;
  /** What it found. */
  evidence: string;
  /** The supporting detail. */
  detail: string;
};

const CLAIMS: readonly Claim[] = [
  {
    claim: "React",
    source: "GITHUB",
    evidence: "1,284 commits",
    detail: "12 repositories, 3 shipped",
  },
  {
    claim: "Python",
    source: "ASSESSMENT",
    evidence: "93rd percentile",
    detail: "timed problem, full transcript",
  },
  {
    claim: "AI / ML",
    source: "PROJECTS",
    evidence: "4 shipped systems",
    detail: "architecture reviewed",
  },
  {
    claim: "Team leadership",
    source: "HACKATHONS",
    evidence: "3 events, 1 win",
    detail: "contribution verified per member",
  },
  {
    claim: "5 years experience",
    source: "TIMELINE",
    evidence: "consistent since 2021",
    detail: "no unexplained gaps",
  },
] as const;

/** Beat table, kept in one place so the choreography is readable at a glance. */
const CLAIM_MS = 900;
const RESOLVE_AT = CLAIM_MS * CLAIMS.length + 400;
const CYCLE = RESOLVE_AT + 5200;

type Phase = { traced: number; resolved: boolean };
const START: Phase = { traced: 0, resolved: false };

function reduce(state: Phase, action: "trace" | "resolve" | "reset"): Phase {
  switch (action) {
    case "trace":
      return { ...state, traced: Math.min(state.traced + 1, CLAIMS.length) };
    case "resolve":
      return { ...state, resolved: true };
    case "reset":
      return START;
  }
}

export function ResumeDissolve({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [phase, dispatch] = useReducer(reduce, START);

  // Latched: disconnects on first intersection. A non-latched observer re-fired on every
  // scroll nudge and restarted the sequence mid-flight, which reads as a frozen
  // animation rather than a looping one.
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

  const animating = armed && onScreen && !reduced;

  useEffect(() => {
    if (!animating) return;
    // One interval drives the whole cycle: it advances a tick counter and derives every
    // beat from it, so there is no nest of timers to leak or fall out of step.
    const TICKS = Math.round(CYCLE / CLAIM_MS);
    let tick = 0;
    const timer = setInterval(() => {
      tick = (tick + 1) % TICKS;
      if (tick === 0) {
        dispatch("reset");
        return;
      }
      if (tick <= CLAIMS.length) dispatch("trace");
      else if (tick === CLAIMS.length + 1) dispatch("resolve");
    }, CLAIM_MS);
    return () => clearInterval(timer);
  }, [animating]);

  // With motion off, the finished state *is* the render: the frame has to make its point
  // for a visitor who never sees it move.
  const traced = animating ? phase.traced : CLAIMS.length;
  const resolved = animating ? phase.resolved : true;

  return (
    <div ref={ref} className={cn("relative", className)}>
      <div className="flex items-center justify-between gap-3 pb-4">
        <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
          {traced < CLAIMS.length ? "Tracing claims" : "Evidence resolved"}
        </p>
        <span className="flex items-center gap-1.5 font-mono text-meta text-muted-foreground">
          <span
            aria-hidden
            className={
              traced < CLAIMS.length
                ? "size-1.5 animate-pulse rounded-full bg-primary"
                : "size-1.5 rounded-full bg-success"
            }
          />
          {traced} / {CLAIMS.length}
        </span>
      </div>

      <ul className="divide-hairline" aria-live="polite">
        {CLAIMS.map((item, i) => {
          const done = i < traced;
          return (
            <li key={item.claim} className="grid grid-cols-[minmax(0,auto)_auto_minmax(0,1fr)] items-center gap-4 py-3.5 sm:gap-6">
              {/* The claim, struck through once its evidence lands. */}
              <span className="relative min-w-0">
                <span
                  className={cn(
                    "block truncate text-section transition-colors duration-(--animate-duration-base)",
                    done ? "text-muted-foreground/50" : "text-foreground",
                  )}
                >
                  {item.claim}
                </span>
                <motion.span
                  aria-hidden
                  className="absolute inset-x-0 top-1/2 h-px origin-left bg-muted-foreground/50"
                  initial={false}
                  animate={{ scaleX: done ? 1 : 0 }}
                  transition={{ duration: reduced ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
                />
              </span>

              {/* The evidence line: the claim physically reaching its source. */}
              <motion.span
                aria-hidden
                className="h-px w-8 origin-left bg-primary sm:w-14"
                initial={false}
                animate={{ scaleX: done ? 1 : 0 }}
                transition={{ duration: reduced ? 0 : 0.35, ease: [0.22, 1, 0.36, 1] }}
              />

              <motion.span
                className="min-w-0"
                initial={false}
                animate={{ opacity: done ? 1 : 0, x: done ? 0 : reduced ? 0 : -6 }}
                transition={{ duration: reduced ? 0 : 0.35, delay: reduced ? 0 : 0.1 }}
              >
                <span className="block font-mono text-[0.6875rem] tracking-[0.12em] text-primary uppercase">
                  {item.source}
                </span>
                <span className="block truncate text-body font-medium text-foreground">
                  {item.evidence}
                </span>
                <span className="block truncate text-meta text-muted-foreground">
                  {item.detail}
                </span>
              </motion.span>
            </li>
          );
        })}
      </ul>

      {/* What the evidence adds up to.
          The score is the conclusion of the whole sequence, so it is set as a visual
          object rather than tucked into a KPI row: at display scale it becomes the second
          thing the eye lands on after the headline, and it deliberately hangs left of the
          evidence column so the hero is not two tidy stacked rectangles. */}
      <motion.div
        className="relative mt-8 lg:-ml-16 xl:-ml-24"
        initial={false}
        animate={{ opacity: resolved ? 1 : 0.35 }}
        transition={{ duration: reduced ? 0 : 0.5 }}
      >
        <div className="flex flex-wrap items-end gap-x-10 gap-y-5">
          <div className="relative">
            <p className="font-mono text-meta font-medium tracking-[0.14em] text-primary uppercase">
              Talent score
            </p>
            <p className="mt-1 font-mono text-[clamp(4.5rem,2rem+7vw,8.5rem)] leading-[0.82] font-medium tracking-[-0.04em] text-foreground">
              <ScoreDigits resolved={resolved} animating={animating} />
            </p>
          </div>

          <dl className="flex flex-wrap gap-x-8 gap-y-3 pb-2">
            {[
              ["Signals", "47"],
              ["Sources", "8"],
              ["Confidence", "High"],
            ].map(([k, v], i) => (
              <motion.div
                key={k}
                initial={false}
                animate={{ opacity: resolved ? 1 : 0, y: resolved ? 0 : reduced ? 0 : 6 }}
                transition={{
                  duration: reduced ? 0 : 0.4,
                  delay: reduced || !resolved ? 0 : 0.15 + i * 0.08,
                }}
              >
                <dt className="font-mono text-[0.6875rem] tracking-[0.12em] text-muted-foreground uppercase">
                  {k}
                </dt>
                <dd
                  data-numeric
                  className="mt-0.5 font-mono text-body font-medium text-foreground"
                >
                  {v}
                </dd>
              </motion.div>
            ))}
          </dl>
        </div>
      </motion.div>
    </div>
  );
}

const SCORE = 82.4;

/** Counts to the score once the evidence resolves, and re-counts on every cycle.
 *
 * Writes to a ref-held node rather than through state, so the count does not re-render
 * the scene sixty times a second. Numbers on this page should feel arrived at rather
 * than simply printed - the count *is* the argument that a score is computed from
 * something. */
function ScoreDigits({
  resolved,
  animating,
}: {
  resolved: boolean;
  animating: boolean;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (!animating || !resolved) {
      node.textContent = resolved ? SCORE.toFixed(1) : "--";
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / 1100, 1);
      // easeOutCubic: the figure settles rather than stopping dead.
      node.textContent = (SCORE * (1 - Math.pow(1 - t, 3))).toFixed(1);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [resolved, animating]);

  return (
    <span ref={ref} data-numeric>
      {SCORE.toFixed(1)}
    </span>
  );
}
