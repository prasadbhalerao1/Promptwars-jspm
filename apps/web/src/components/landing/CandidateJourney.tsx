"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Signature moment 04: one candidate travelling the whole pipeline.
 *
 * The differentiator TRACE actually claims - that a hackathon is the front of a hiring
 * pipeline rather than an event that ends in a photograph - is a claim about continuity.
 * Seven cards in a row would break exactly the thing being argued.
 *
 * So it is one card that transforms. The person is constant; what the system knows about
 * them accumulates, and the card's title, evidence and status change around that. The
 * stage list beside it is the reading of what changed.
 */

type Stage = {
  stage: string;
  /** What the candidate is *to the system* at this point. */
  title: string;
  status: string;
  /** The evidence that exists by this stage. Rows accumulate rather than swap. */
  facts: readonly (readonly [string, string])[];
};

const STAGES: readonly Stage[] = [
  {
    stage: "Hackathon",
    title: "Team member",
    status: "Submitted",
    facts: [["Team", "Ledgerline"]],
  },
  {
    stage: "Contribution analysis",
    title: "Top contributor",
    status: "Analyzed",
    facts: [
      ["Team", "Ledgerline"],
      ["Commits", "208"],
      ["Pull requests", "27"],
    ],
  },
  {
    stage: "Project and deck",
    title: "Project author",
    status: "Scored",
    facts: [
      ["Commits", "208"],
      ["Deck score", "92"],
      ["Architecture", "Corroborated"],
    ],
  },
  {
    stage: "Verification",
    title: "Verified talent",
    status: "Verified",
    facts: [
      ["Authorship", "Confirmed"],
      ["Certificates", "2 of 2"],
      ["Confidence", "High"],
    ],
  },
  {
    stage: "Talent profile",
    title: "Talent profile",
    status: "Resolved",
    facts: [
      ["Talent score", "82.4"],
      ["Signals", "47"],
      ["Sources", "8"],
    ],
  },
  {
    stage: "Discovery",
    title: "94% match",
    status: "Shortlisted",
    facts: [
      ["Skill overlap", "96"],
      ["Project relevance", "93"],
      ["Verified evidence", "95"],
    ],
  },
  {
    stage: "Interview",
    title: "Strong hire",
    status: "Recommended",
    facts: [
      ["Reasoning", "95"],
      ["Technical depth", "92"],
      ["Transcript", "Attached"],
    ],
  },
] as const;

const STAGE_MS = 1700;

export function CandidateJourney({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [index, setIndex] = useState(0);

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
    const timer = setInterval(
      () => setIndex((i) => (i + 1) % STAGES.length),
      STAGE_MS,
    );
    return () => clearInterval(timer);
  }, [animating]);

  // Static state shows the end of the journey: the hire is the point being made.
  const current = animating ? index : STAGES.length - 1;
  const stage = STAGES[current];

  return (
    <div
      ref={ref}
      className={cn("grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-12", className)}
    >
      {/* The run. Each stage is a step the card has already passed through. */}
      <ol className="relative">
        <span aria-hidden className="absolute inset-y-2 left-[3.5px] w-px bg-border" />
        {STAGES.map((s, i) => {
          const passed = i <= current;
          return (
            <li key={s.stage} className="relative flex items-start gap-4 py-2.5">
              <motion.span
                aria-hidden
                className={cn(
                  "mt-1.5 size-2 shrink-0 rounded-full",
                  passed ? "bg-primary" : "bg-border",
                )}
                initial={false}
                animate={{ scale: i === current ? 1.5 : 1 }}
                transition={{ type: "spring", stiffness: 320, damping: 22 }}
              />
              <motion.span
                className={cn(
                  "text-body",
                  i === current
                    ? "font-medium text-foreground"
                    : passed
                      ? "text-muted-foreground"
                      : "text-muted-foreground/45",
                )}
                initial={false}
                animate={{ opacity: passed ? 1 : 0.55 }}
                transition={{ duration: reduced ? 0 : 0.3 }}
              >
                {s.stage}
              </motion.span>
            </li>
          );
        })}
      </ol>

      {/* The card. One object throughout - the person does not change, only what is
          known about them. `layout` lets it resize as evidence accumulates rather than
          jumping between fixed heights. */}
      <motion.div
        layout={animating}
        transition={{ type: "spring", stiffness: 260, damping: 30 }}
        className="self-start rounded-xl bg-card p-6 shadow-raised"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-muted font-mono text-body font-medium text-primary"
            >
              AC
            </span>
            <div>
              <p className="text-section font-medium text-foreground">Alice Chen</p>
              {/* The title is what transforms: team member becomes strong hire. */}
              {/* No AnimatePresence: an exiting node lingers at opacity 0, which leaves
                  the title slot momentarily blank and reads as a flicker. Keying the
                  element re-mounts it, so the new title fades in over nothing. */}
              <motion.p
                key={stage.title}
                initial={animating ? { opacity: 0, y: 6 } : false}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : 0.28 }}
                className="font-mono text-meta tracking-[0.12em] text-primary uppercase"
              >
                {stage.title}
              </motion.p>
            </div>
          </div>
          <motion.span
            key={stage.status}
            initial={animating ? { opacity: 0, scale: 0.9 } : false}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: reduced ? 0 : 0.28 }}
            className="flex shrink-0 items-center gap-1.5 rounded-full bg-surface-sunken px-2.5 py-1 text-meta font-medium text-foreground"
          >
            <Check aria-hidden className="size-3.5 text-success" />
            {stage.status}
          </motion.span>
        </div>

        <dl className="mt-5 divide-hairline">
          <AnimatePresence initial={false} mode="popLayout">
            {stage.facts.map((fact) => (
              <motion.div
                key={fact[0]}
                layout={animating}
                initial={{ opacity: 0, y: reduced ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.3 }}
                className="flex items-baseline justify-between gap-4 py-2.5 first:pt-0"
              >
                <dt className="text-body text-muted-foreground">{fact[0]}</dt>
                <dd
                  data-numeric
                  className="font-mono text-body font-medium text-foreground"
                >
                  {fact[1]}
                </dd>
              </motion.div>
            ))}
          </AnimatePresence>
        </dl>
      </motion.div>
    </div>
  );
}
