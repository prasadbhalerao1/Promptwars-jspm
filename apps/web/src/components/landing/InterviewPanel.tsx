"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity, MessageSquare } from "lucide-react";

import { cn } from "@/lib/utils";

/** The AI interview, as an evaluation instrument rather than a video call.
 *
 * There is no avatar, no waveform and no fake webcam here on purpose: the product's
 * claim is that the interview produces a *scored, evidenced report*, and the interesting
 * surface is the reasoning being measured, not a face. So the frame is an instrument
 * panel — question, streaming answer, live reasoning meters, signals detected.
 *
 * Dramatic without going dark, per the light-only rule: the drama comes from the analysis
 * states and the scan line, not from a black background.
 */

const QUESTION =
  "Your ingestion pipeline drops events under load. Walk me through how you'd find the bottleneck.";

/** Streamed in word groups rather than characters: a character-by-character crawl of a
 * 60-word answer takes far too long to hold attention, and word-level streaming is what
 * a real token stream looks like anyway. */
const ANSWER = [
  "I'd start by measuring rather than guessing:",
  "add tracing at each stage boundary so I can see",
  "where latency accumulates. If the consumer lag grows",
  "while CPU stays flat, the bottleneck is downstream I/O,",
  "not processing. From there I'd put a bounded queue",
  "in front of the writer with explicit backpressure,",
  "so we shed load deliberately instead of dropping",
  "events silently.",
] as const;

const METERS = [
  { label: "Technical depth", value: 92 },
  { label: "System thinking", value: 95 },
  { label: "Communication", value: 88 },
  { label: "Tradeoff reasoning", value: 91 },
] as const;

/** Signals the evaluator raises as the answer arrives, each quoting the words that
 * produced it. Naming the evidence is the whole point: an evaluation that just asserts
 * "system thinking 95" is the thing this product exists to replace. */
const SIGNALS = [
  { phrase: "measuring rather than guessing", signal: "Diagnostic reasoning" },
  { phrase: "tracing at each stage boundary", signal: "Instrumentation" },
  { phrase: "bounded queue", signal: "System design" },
  { phrase: "explicit backpressure", signal: "Failure mode awareness" },
] as const;

/** The answer as a reasoning graph.
 *
 * This is the signature of the interview scene: TRACE claims to evaluate *how someone
 * thinks*, and a list of scores cannot show that. The chain is extracted from the same
 * answer streaming beside it, so the two halves are visibly the same content read two
 * ways. */
const REASONING = [
  "Measure",
  "Instrument",
  "Locate bottleneck",
  "Bounded queue",
  "Backpressure",
  "Deliberate shedding",
] as const;

/** Per-question reasoning scores across the session. Question 3 is the one being
 * transcribed above, so the curve gives the single exchange its context: this is a
 * five-question evaluation, not one clever answer. */
const CURVE = [
  { q: "Q1", value: 78 },
  { q: "Q2", value: 84 },
  { q: "Q3", value: 95 },
  { q: "Q4", value: 89 },
  { q: "Q5", value: 92 },
] as const;

const WORD_MS = 300;
/** Stream time plus a hold on the finished report before the loop wraps. */
const CYCLE = ANSWER.length * WORD_MS + 6000;

export function InterviewPanel() {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [spoken, setSpoken] = useState(0);

  // Latched: disconnects on first intersection. A re-firing observer restarts the
  // sequence mid-flight, which reads as a frozen animation rather than a looping one.
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
    if (!animating) return;

    // One interval drives the whole loop: it streams the answer word by word, then keeps
    // ticking through a hold at the end before wrapping back to zero. Nesting a second
    // interval inside a restart timer was the alternative, and it leaked one on every
    // cycle.
    const TICKS = Math.round(CYCLE / WORD_MS);
    let tick = 0;
    const timer = setInterval(() => {
      tick = (tick + 1) % TICKS;
      setSpoken(Math.min(tick, ANSWER.length));
    }, WORD_MS);

    return () => clearInterval(timer);
  }, [animating]);

  // Static state renders complete — the panel has to make its point with motion off.
  const shown = animating ? spoken : ANSWER.length;
  const done = shown >= ANSWER.length;
  // Signals arrive as the answer earns them rather than all at once at the end.
  const signalsShown = animating
    ? Math.floor((shown / ANSWER.length) * SIGNALS.length)
    : SIGNALS.length;

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-xl bg-card shadow-raised"
    >
      {/* The scan line: one slow sweep, low opacity. This is the whole "the machine is
          reading you" effect, and at any stronger opacity it becomes a gimmick. */}
      {animating ? (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-10 h-24 bg-[linear-gradient(to_bottom,transparent,color-mix(in_oklch,var(--primary)_7%,transparent),transparent)]"
          animate={{ y: ["-6rem", "100%"] }}
          transition={{ duration: 5.5, repeat: Infinity, ease: "linear" }}
        />
      ) : null}

      <div className="flex items-center justify-between gap-3 px-5 py-3.5 sm:px-6">
        <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
          Interview · Question 3 of 5
        </p>
        <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
          <span
            aria-hidden
            className={
              done
                ? "size-1.5 rounded-full bg-success"
                : "size-1.5 animate-pulse rounded-full bg-primary"
            }
          />
          {done ? "Evaluated" : "Analyzing"}
        </span>
      </div>

      <div className="grid gap-px bg-border lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        {/* Transcript. */}
        <div className="bg-card p-5 sm:p-6">
          <div className="flex gap-3">
            <span
              aria-hidden
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-muted-foreground"
            >
              <MessageSquare aria-hidden className="size-3.5" />
            </span>
            <p className="text-lead leading-relaxed font-medium text-foreground">
              {QUESTION}
            </p>
          </div>

          <div className="mt-5 flex gap-3">
            <span
              aria-hidden
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-muted font-mono text-meta font-medium text-primary"
            >
              AC
            </span>
            <p className="text-body leading-relaxed text-muted-foreground" aria-live="polite">
              {ANSWER.slice(0, shown).map((chunk, i) => (
                <motion.span
                  key={i}
                  initial={false}
                  animate={{ opacity: 1 }}
                  className="text-foreground"
                >
                  {chunk}{" "}
                </motion.span>
              ))}
              {animating && !done ? (
                <span
                  aria-hidden
                  className="ml-px inline-block h-4 w-px translate-y-0.5 animate-pulse bg-primary align-middle"
                />
              ) : null}
            </p>
          </div>

          {/* The session, not just this answer. Bars rather than a line chart: at this
              size a smoothed curve implies precision the five discrete scores do not
              have. */}
          <div className="mt-8 border-t border-border pt-5">
            <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
              Reasoning across the session
            </p>
            <ol className="mt-4 flex items-end gap-3">
              {CURVE.map((point, i) => {
                const current = point.q === "Q3";
                return (
                  <li key={point.q} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                    <span
                      data-numeric
                      className={cn(
                        "font-mono text-meta",
                        current ? "font-medium text-primary" : "text-muted-foreground",
                      )}
                    >
                      {point.value}
                    </span>
                    <div
                      aria-hidden
                      className="flex h-24 w-full items-end justify-center sm:h-28"
                    >
                      <motion.span
                        className={cn(
                          "w-full max-w-10 origin-bottom rounded-t-sm",
                          current ? "bg-primary" : "bg-border",
                        )}
                        // Full height, scaled on Y. A percentage height here resolved
                        // against an indefinite flex height and rendered every bar the
                        // same size; scaleY also keeps this off the layout path.
                        style={{ height: "100%" }}
                        initial={animating ? { scaleY: 0 } : false}
                        animate={{ scaleY: point.value / 100 }}
                        transition={{
                          duration: reduced ? 0 : 0.7,
                          delay: reduced ? 0 : 0.2 + i * 0.09,
                          ease: [0.22, 1, 0.36, 1],
                        }}
                      />
                    </div>
                    <span
                      className={cn(
                        "font-mono text-meta",
                        current ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {point.q}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>

        {/* Live evaluation. */}
        <div className="bg-card p-5 sm:p-6">
          <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Reasoning
          </p>
          <dl className="mt-4 space-y-3.5">
            {METERS.map((m) => {
              // Meters fill in step with the answer, so the score is visibly being
              // *earned* rather than revealed at the end.
              const progress = animating ? shown / ANSWER.length : 1;
              return (
                <div key={m.label}>
                  <div className="flex items-baseline justify-between gap-3">
                    <dt className="text-meta text-muted-foreground">{m.label}</dt>
                    <dd
                      data-numeric
                      className="font-mono text-meta font-medium text-foreground"
                    >
                      {Math.round(m.value * progress)}
                    </dd>
                  </div>
                  <div
                    aria-hidden
                    className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-surface-sunken"
                  >
                    <motion.div
                      className="h-full rounded-full bg-primary"
                      initial={false}
                      animate={{ width: `${m.value * progress}%` }}
                      transition={{ duration: reduced ? 0 : 0.4, ease: "easeOut" }}
                    />
                  </div>
                </div>
              );
            })}
          </dl>

          {/* The reasoning graph: the answer read as a chain of thought rather than as
              a block of text. Nodes light as the words that earned them arrive. */}
          <p className="mt-6 font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Reasoning path
          </p>
          <ol className="mt-3">
            {REASONING.map((node, i) => {
              const at = ((i + 1) / REASONING.length) * ANSWER.length;
              const lit = shown >= at;
              return (
                <li key={node} className="relative flex items-center gap-2.5 py-1">
                  {i < REASONING.length - 1 ? (
                    <motion.span
                      aria-hidden
                      className="absolute top-4.5 left-[3px] h-4 w-px origin-top bg-primary/40"
                      initial={false}
                      animate={{ scaleY: lit ? 1 : 0 }}
                      transition={{ duration: reduced ? 0 : 0.3 }}
                    />
                  ) : null}
                  <motion.span
                    aria-hidden
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      lit ? "bg-primary" : "bg-border",
                    )}
                    initial={false}
                    animate={{ scale: lit ? 1 : 0.7 }}
                    transition={{ duration: reduced ? 0 : 0.25 }}
                  />
                  <motion.span
                    className={cn(
                      "text-meta",
                      lit ? "font-medium text-foreground" : "text-muted-foreground/50",
                    )}
                    initial={false}
                    animate={{ opacity: lit ? 1 : 0.45 }}
                    transition={{ duration: reduced ? 0 : 0.3 }}
                  >
                    {node}
                  </motion.span>
                </li>
              );
            })}
          </ol>

          <p className="mt-6 font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Signals
          </p>
          <ul className="mt-3 space-y-2.5">
            <AnimatePresence initial={false}>
              {SIGNALS.slice(0, signalsShown).map((s) => (
                <motion.li
                  key={s.signal}
                  initial={{ opacity: 0, y: reduced ? 0 : 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: reduced ? 0 : 0.35 }}
                  className="flex items-start gap-2"
                >
                  <Activity
                    aria-hidden
                    className="mt-0.5 size-3.5 shrink-0 text-primary"
                  />
                  <span className="min-w-0">
                    <span className="block text-meta font-medium text-foreground">
                      {s.signal}
                    </span>
                    {/* The quoted words are the evidence for the signal above them. */}
                    <span className="block truncate text-meta text-muted-foreground italic">
                      &ldquo;{s.phrase}&rdquo;
                    </span>
                  </span>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>

          <AnimatePresence>
            {done ? (
              <motion.div
                initial={{ opacity: 0, y: reduced ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.45 }}
                className="mt-6 rounded-lg bg-surface-sunken p-4"
              >
                <p className="text-meta text-muted-foreground">Recommendation</p>
                <p className="mt-1 text-body font-medium text-foreground">
                  Strong hire for senior backend
                </p>
                <p className="mt-1.5 text-meta leading-relaxed text-muted-foreground">
                  Based on five answers and the full transcript, which is attached to
                  the report.
                </p>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
