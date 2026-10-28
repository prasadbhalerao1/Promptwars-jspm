"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Scene 06: verification signals converging on one candidate.
 *
 * The previous version was a bordered list of checks beside a headline, which stated the
 * idea without showing it. The claim TRACE makes here is specifically about *convergence
 * and restraint*: independent sources are checked, they arrive from different directions,
 * and what comes out is an evidence strength with an open review queue - never a verdict.
 * A diagram can carry that; a list of green ticks actively works against it, because a
 * column of ticks reads as "all clear" which is the one thing this system must not say.
 *
 * So the one signal that needs a human lands last and stays amber, and the centre reports
 * confidence rather than a pass.
 */

const VB = { w: 940, h: 470 };
const CX = VB.w / 2;
const CY = VB.h / 2;
const RADIUS = 196;

type Check = {
  label: string;
  /** `review` is not a failure. It is a finding a person has to weigh. */
  state: "verified" | "review";
  detail: string;
};

/** Seven sources, checked independently. Ordered so the one needing review sits last in
 * the sequence and is the state the viewer is left looking at. */
const CHECKS: readonly Check[] = [
  { label: "Commit history", state: "verified", detail: "authorship consistent" },
  { label: "Certificates", state: "verified", detail: "2 of 2 issuers matched" },
  { label: "Project authorship", state: "verified", detail: "no imported bulk commits" },
  { label: "Identity", state: "verified", detail: "no duplicate profiles" },
  { label: "Assessment", state: "verified", detail: "session unbroken" },
  { label: "Submission", state: "verified", detail: "timestamps consistent" },
  { label: "AI-generated content", state: "review", detail: "review recommended" },
] as const;

const STEP_MS = 620;
const CYCLE = STEP_MS * (CHECKS.length + 5);

/** Node positions on an arc around the candidate. Not a full circle: leaving the right
 * side open lets the composition breathe and stops it reading as a clock face. */
function nodeAt(i: number, total: number) {
  // -140deg to +140deg, so the ring opens toward the reader rather than closing.
  const spread = (280 * Math.PI) / 180;
  const angle = -Math.PI / 2 - spread / 2 + (i / (total - 1)) * spread;
  return {
    x: CX + Math.cos(angle) * RADIUS,
    y: CY + Math.sin(angle) * RADIUS,
    angle,
  };
}

export function VerificationField({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [tick, setTick] = useState(0);

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
    const TICKS = Math.round(CYCLE / STEP_MS);
    let t = 0;
    const timer = setInterval(() => {
      t = (t + 1) % TICKS;
      setTick(t);
    }, STEP_MS);
    return () => clearInterval(timer);
  }, [animating]);

  // Motion off renders the resolved state: the diagram has to make its point for anyone
  // who never sees it move.
  const checked = animating ? Math.min(tick, CHECKS.length) : CHECKS.length;
  const resolved = checked >= CHECKS.length;

  return (
    <div ref={ref} className={cn("relative", className)}>
      {/* Phone composition: the ring becomes a vertical run. Same seven sources, same
          amber hold, but at a size a thumb-held screen can actually read. */}
      <ul className="lg:hidden">
        {CHECKS.map((check, i) => {
          const done = i < checked;
          const review = check.state === "review";
          return (
            <li
              key={check.label}
              className="relative flex items-start gap-3.5 py-3"
            >
              {i < CHECKS.length - 1 ? (
                <motion.span
                  aria-hidden
                  className={cn(
                    "absolute top-7 left-[5px] w-px origin-top",
                    review ? "bg-warning/40" : "bg-primary/30",
                  )}
                  style={{ bottom: 0 }}
                  initial={false}
                  animate={{ scaleY: done ? 1 : 0 }}
                  transition={{ duration: reduced ? 0 : 0.35 }}
                />
              ) : null}
              <motion.span
                aria-hidden
                className={cn(
                  "mt-1.5 size-2.5 shrink-0 rounded-full",
                  done
                    ? review
                      ? "bg-warning"
                      : "bg-primary"
                    : "bg-border",
                )}
                initial={false}
                animate={{ scale: done ? 1 : 0.75 }}
                transition={{ type: "spring", stiffness: 320, damping: 22 }}
              />
              <motion.span
                className="min-w-0 flex-1"
                initial={false}
                animate={{ opacity: done ? 1 : 0.4 }}
                transition={{ duration: reduced ? 0 : 0.35 }}
              >
                <span className="block text-body font-medium text-foreground">
                  {check.label}
                </span>
                <span
                  className={cn(
                    "block font-mono text-meta tracking-[0.1em] uppercase",
                    review ? "text-warning" : "text-muted-foreground",
                  )}
                >
                  {done ? check.detail : "checking"}
                </span>
              </motion.span>
            </li>
          );
        })}
      </ul>

      {/* The conclusion, phone-sized. */}
      <motion.div
        className="mt-6 flex items-baseline gap-4 border-t border-border pt-5 lg:hidden"
        initial={false}
        animate={{ opacity: resolved ? 1 : 0.4 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
      >
        <span className="font-mono text-meta tracking-[0.12em] text-muted-foreground uppercase">
          Evidence
        </span>
        <span
          data-numeric
          className="font-mono text-[3rem] leading-none font-medium text-foreground"
        >
          {resolved ? "94" : "--"}
        </span>
        <span className="font-mono text-meta tracking-[0.12em] text-muted-foreground uppercase">
          Strength high
        </span>
      </motion.div>

      <svg
        // Laptop only: the ring needs room for seven labelled nodes, and the phone shows
        // the vertical run above instead.
        viewBox={`0 0 ${VB.w} ${VB.h}`}
        className="hidden h-auto w-full lg:block"
        role="img"
        aria-label="Seven verification sources - commit history, certificates, project authorship, identity, assessment, submission and AI-generated content - converging on one candidate. Six resolve as verified; the AI-content signal is held for human review. Evidence strength resolves to 94 with one signal in the review queue."
      >
        {/* Connections first, so nodes paint over their endpoints. */}
        {CHECKS.map((check, i) => {
          const n = nodeAt(i, CHECKS.length);
          const done = i < checked;
          const review = check.state === "review";
          return (
            <motion.line
              key={`line-${check.label}`}
              x1={n.x}
              y1={n.y}
              x2={CX}
              y2={CY}
              stroke={review ? "var(--warning)" : "var(--primary)"}
              strokeOpacity={review ? 0.55 : 0.4}
              strokeWidth={1.25}
              initial={false}
              animate={{ pathLength: done ? 1 : 0, opacity: done ? 1 : 0 }}
              transition={{
                duration: reduced ? 0 : 0.5,
                ease: [0.22, 1, 0.36, 1],
              }}
            />
          );
        })}

        {/* A pulse travelling inward on each resolved connection: the check arriving. */}
        {animating && !reduced
          ? CHECKS.slice(0, checked).map((check, i) => {
              const n = nodeAt(i, CHECKS.length);
              return (
                <circle
                  key={`pulse-${check.label}`}
                  r={2.5}
                  fill={
                    check.state === "review" ? "var(--warning)" : "var(--primary)"
                  }
                >
                  <animateMotion
                    dur="1.8s"
                    begin={`${i * 0.2}s`}
                    repeatCount="indefinite"
                    path={`M ${n.x} ${n.y} L ${CX} ${CY}`}
                  />
                  <animate
                    attributeName="opacity"
                    values="0;1;1;0"
                    dur="1.8s"
                    begin={`${i * 0.2}s`}
                    repeatCount="indefinite"
                  />
                </circle>
              );
            })
          : null}

        {/* The sources. */}
        {CHECKS.map((check, i) => {
          const n = nodeAt(i, CHECKS.length);
          const done = i < checked;
          const review = check.state === "review";
          // Labels on the left half of the arc read outward to the left.
          const left = n.x < CX;
          return (
            <motion.g
              key={check.label}
              initial={false}
              animate={{ opacity: done ? 1 : 0.28 }}
              transition={{ duration: reduced ? 0 : 0.4 }}
            >
              <circle
                cx={n.x}
                cy={n.y}
                r={7}
                fill={
                  done
                    ? review
                      ? "var(--warning)"
                      : "var(--primary)"
                    : "var(--border)"
                }
              />
              <text
                x={left ? n.x - 16 : n.x + 16}
                y={n.y - 2}
                textAnchor={left ? "end" : "start"}
                className="fill-foreground text-[13px] font-medium"
              >
                {check.label}
              </text>
              <text
                x={left ? n.x - 16 : n.x + 16}
                y={n.y + 15}
                textAnchor={left ? "end" : "start"}
                className={cn(
                  "font-mono text-[10.5px] tracking-[0.1em]",
                  review ? "fill-warning" : "fill-muted-foreground",
                )}
              >
                {done ? check.detail.toUpperCase() : "CHECKING"}
              </text>
            </motion.g>
          );
        })}

        {/* The candidate at the centre: what everything is being checked against. */}
        <circle
          cx={CX}
          cy={CY}
          r={74}
          fill="var(--card)"
          stroke="var(--border)"
        />
        <motion.circle
          cx={CX}
          cy={CY}
          r={74}
          fill="none"
          stroke="var(--primary)"
          strokeOpacity={0.4}
          initial={false}
          animate={{ scale: resolved ? 1 : 0.94 }}
          style={{ transformOrigin: `${CX}px ${CY}px` }}
          transition={{ type: "spring", stiffness: 220, damping: 24 }}
        />
        <text
          x={CX}
          y={CY - 22}
          textAnchor="middle"
          className="fill-muted-foreground font-mono text-[10.5px] tracking-[0.14em]"
        >
          EVIDENCE
        </text>
        <text
          x={CX}
          y={CY + 16}
          textAnchor="middle"
          className="fill-foreground font-mono text-[40px] font-medium"
        >
          {resolved ? "94" : "--"}
        </text>
        <text
          x={CX}
          y={CY + 40}
          textAnchor="middle"
          className="fill-muted-foreground font-mono text-[10.5px] tracking-[0.14em]"
        >
          STRENGTH
        </text>
      </svg>

      {/* The review queue, in text. This is the honest reading of the diagram: six
          resolved, one held, nothing decided. It is real DOM content rather than SVG type
          so it is readable on a phone and available to a screen reader. */}
      <motion.dl
        className="mt-6 hidden flex-wrap gap-x-10 gap-y-4 border-t border-border pt-5 lg:flex"
        initial={false}
        animate={{ opacity: resolved ? 1 : 0.4 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
      >
        {[
          ["Checks resolved", "6"],
          ["Awaiting review", "1"],
          ["Evidence strength", "High"],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="font-mono text-[0.6875rem] tracking-[0.12em] text-muted-foreground uppercase">
              {k}
            </dt>
            <dd
              data-numeric
              className="mt-1 font-mono text-section font-medium text-foreground"
            >
              {v}
            </dd>
          </div>
        ))}
      </motion.dl>
    </div>
  );
}
