"use client";

import { useEffect, useId, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, Check } from "lucide-react";

import { cn } from "@/lib/utils";

/** Two ways TRACE reads work that already exists: a pitch deck, and a repository.
 *
 * One frame, two tabs, because these are the same idea — evidence the candidate produced
 * before ever meeting a recruiter — and two separate sections would say it twice.
 *
 * The tabs are real controls, not a decorative toggle: this is the one place on the page
 * where the visitor drives the demo, which is worth more than a third autoplaying loop.
 */

const SLIDES = [
  { n: "01", title: "Problem", note: "Clear, specific, well scoped", ok: true },
  { n: "02", title: "Solution", note: "Architecture matches the repository", ok: true },
  { n: "03", title: "Traction", note: "Figures cited without a source", ok: false },
  { n: "04", title: "Market", note: "Sizing appears weak, top-down only", ok: false },
  { n: "05", title: "Team", note: "Roles corroborated by commit history", ok: true },
] as const;

const DECK_SCORES = [
  { label: "Problem clarity", value: 91 },
  { label: "Innovation", value: 84 },
  { label: "Business potential", value: 72 },
  { label: "Technical feasibility", value: 88 },
] as const;

const LANGUAGES = [
  { label: "TypeScript", pct: 46 },
  { label: "Python", pct: 31 },
  { label: "Go", pct: 14 },
  { label: "Other", pct: 9 },
] as const;

const DNA = [
  { label: "Test coverage", value: 78 },
  { label: "Review participation", value: 86 },
  { label: "Commit consistency", value: 89 },
  { label: "Deployment maturity", value: 74 },
] as const;

/** 26 weeks of contribution density. Hand-written rather than random so the pattern is
 * stable between renders and reads as a real history — a burst around a hackathon, a
 * quiet fortnight, a sustained run — instead of noise. */
const HEATMAP = [
  1, 2, 1, 0, 2, 3, 2, 1, 0, 1, 3, 4, 4, 3, 2, 0, 1, 2, 3, 4, 3, 2, 3, 4, 4, 3,
  0, 1, 2, 2, 3, 2, 1, 0, 0, 2, 3, 3, 4, 2, 1, 1, 2, 3, 4, 4, 2, 1, 2, 3, 4, 3,
  2, 0, 1, 3, 3, 2, 1, 1, 2, 2, 4, 4, 3, 1, 0, 2, 3, 3, 4, 3, 2, 2, 3, 4, 4, 2,
] as const;

const DENSITY = [
  "bg-surface-sunken",
  "bg-primary/15",
  "bg-primary/35",
  "bg-primary/60",
  "bg-primary/85",
] as const;

type Tab = "deck" | "repo";

export function WorkAnalysis() {
  const [tab, setTab] = useState<Tab>("deck");
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const baseId = useId();

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

  const animate = onScreen && !reduced;

  return (
    <div ref={ref} className="overflow-hidden rounded-xl bg-card shadow-raised">
      {/* Tablist wired for the keyboard: arrow keys move between tabs, which is what a
          screen reader user and a keyboard user both expect from this pattern. */}
      <div
        role="tablist"
        aria-label="What TRACE reads"
        className="flex gap-1 p-2"
        onKeyDown={(e) => {
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          e.preventDefault();
          setTab((t) => (t === "deck" ? "repo" : "deck"));
        }}
      >
        {(
          [
            ["deck", "Pitch deck"],
            ["repo", "Repository"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            id={`${baseId}-tab-${value}`}
            aria-selected={tab === value}
            aria-controls={`${baseId}-panel-${value}`}
            tabIndex={tab === value ? 0 : -1}
            onClick={() => setTab(value)}
            className={cn(
              "rounded-md px-3.5 py-2 text-body font-medium outline-none transition-colors duration-(--animate-duration-fast) focus-visible:ring-3 focus-visible:ring-ring/50",
              tab === value
                ? "bg-primary-muted text-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="border-t border-border p-5 sm:p-6">
        {tab === "deck" ? (
          <div
            role="tabpanel"
            id={`${baseId}-panel-deck`}
            aria-labelledby={`${baseId}-tab-deck`}
            className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]"
          >
            <div className="relative">
              {/* The scan line travels the slide list once per cycle — the deck being
                  read, rather than a static list of findings. */}
              {animate ? (
                <motion.div
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 top-0 z-10 h-16 rounded bg-[linear-gradient(to_bottom,transparent,color-mix(in_oklch,var(--primary)_10%,transparent),transparent)]"
                  animate={{ y: ["-4rem", "100%"] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "linear" }}
                />
              ) : null}
              <ul className="divide-hairline">
                {SLIDES.map((slide) => (
                  <li key={slide.n} className="flex items-start gap-3 py-3 first:pt-0">
                    <span
                      aria-hidden
                      className="mt-0.5 shrink-0 rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-meta text-muted-foreground"
                    >
                      {slide.n}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-body font-medium text-foreground">
                        {slide.title}
                      </p>
                      <p className="text-meta text-muted-foreground">{slide.note}</p>
                    </div>
                    {slide.ok ? (
                      <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-success" />
                    ) : (
                      <AlertTriangle
                        aria-hidden
                        className="mt-0.5 size-4 shrink-0 text-warning"
                      />
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg bg-surface-sunken p-5">
              <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
                Dimensions
              </p>
              <dl className="mt-4 space-y-3.5">
                {DECK_SCORES.map((d, i) => (
                  <Bar key={d.label} {...d} index={i} animate={animate} />
                ))}
              </dl>
              <p className="mt-5 text-meta leading-relaxed text-muted-foreground">
                Findings are cited to the slide that produced them, so a low score is
                something you can argue with.
              </p>
            </div>
          </div>
        ) : (
          <div
            role="tabpanel"
            id={`${baseId}-panel-repo`}
            aria-labelledby={`${baseId}-tab-repo`}
            className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]"
          >
            <div>
              <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
                Contribution history · 26 weeks
              </p>
              <div
                aria-hidden
                className="mt-4 grid grid-flow-col grid-rows-3 gap-1"
                style={{ gridTemplateColumns: "repeat(26, minmax(0, 1fr))" }}
              >
                {HEATMAP.map((level, i) => (
                  <motion.span
                    key={i}
                    className={cn("aspect-square rounded-[2px]", DENSITY[level])}
                    initial={false}
                    animate={{ opacity: onScreen ? 1 : 0 }}
                    transition={{
                      duration: animate ? 0.3 : 0,
                      delay: animate ? (i % 26) * 0.012 : 0,
                    }}
                  />
                ))}
              </div>
              <p className="mt-3 text-meta text-muted-foreground">
                1,284 commits across 12 repositories, with a burst around each hackathon.
              </p>

              <p className="mt-6 font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
                Languages
              </p>
              <div
                aria-hidden
                className="mt-3 flex h-2 overflow-hidden rounded-full bg-surface-sunken"
              >
                {LANGUAGES.map((l, i) => (
                  <motion.span
                    key={l.label}
                    className={
                      ["bg-primary", "bg-info", "bg-success", "bg-border"][i]
                    }
                    initial={false}
                    animate={{ width: onScreen ? `${l.pct}%` : "0%" }}
                    transition={{
                      duration: animate ? 0.7 : 0,
                      delay: animate ? 0.2 + i * 0.08 : 0,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  />
                ))}
              </div>
              <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
                {LANGUAGES.map((l, i) => (
                  <li
                    key={l.label}
                    className="flex items-center gap-1.5 text-meta text-muted-foreground"
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "size-2 rounded-full",
                        ["bg-primary", "bg-info", "bg-success", "bg-border"][i],
                      )}
                    />
                    {l.label} <span data-numeric className="font-mono">{l.pct}%</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg bg-surface-sunken p-5">
              <p className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
                Engineering DNA
              </p>
              <dl className="mt-4 space-y-3.5">
                {DNA.map((d, i) => (
                  <Bar key={d.label} {...d} index={i} animate={animate} />
                ))}
              </dl>
              <p className="mt-5 text-meta leading-relaxed text-muted-foreground">
                Read from the repository itself: tests, reviews, cadence and release
                history, not from what the profile claims.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Bar({
  label,
  value,
  index,
  animate,
}: {
  label: string;
  value: number;
  index: number;
  animate: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-meta text-muted-foreground">{label}</dt>
        <dd data-numeric className="font-mono text-meta font-medium text-foreground">
          {value}
        </dd>
      </div>
      <div
        aria-hidden
        className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-border"
      >
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={false}
          animate={{ width: `${value}%` }}
          transition={{
            duration: animate ? 0.7 : 0,
            delay: animate ? 0.15 + index * 0.08 : 0,
            ease: [0.22, 1, 0.36, 1],
          }}
        />
      </div>
    </div>
  );
}
