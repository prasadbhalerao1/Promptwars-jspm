"use client";

import { useId, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** The signature TRACE effect: a claim traced back to the evidence under it.
 *
 * This is what makes the product's name mean something. Wherever the page states a
 * figure, the figure can be opened to show the chain that produced it - score back
 * through interview, assessment, project, commits - drawn as a cobalt hairline running
 * from conclusion to source.
 *
 * It recurs in every scene deliberately. Nine scenes sharing one interaction language is
 * what makes the page read as a single system rather than as nine stacked pages.
 */

export type EvidenceStep = {
  /** Where this link in the chain came from: `GITHUB`, `INTERVIEW`, `ASSESSMENT`. */
  source: string;
  /** What that source actually showed. */
  detail: string;
};

/** A number with its evidence chain attached.
 *
 * Hover or focus reveals the chain on a pointer device. On touch there is no hover, so
 * the chain renders inline and open - the evidence is the point of the component, and
 * hiding it behind a tap that nothing advertises would make it undiscoverable. That is
 * handled with a CSS media query rather than a UA sniff, so it responds to the actual
 * input the device has.
 */
export function TraceEvidence({
  label,
  value,
  steps,
  className,
}: {
  label: string;
  value: string;
  steps: readonly EvidenceStep[];
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const show = open || !armed;

  return (
    <div
      className={cn("relative", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="group/trace flex w-full items-baseline justify-between gap-4 rounded-sm text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className="text-body text-muted-foreground">{label}</span>
        <span className="flex items-baseline gap-2">
          <span
            data-numeric
            className="font-mono text-section font-medium text-foreground"
          >
            {value}
          </span>
          <span
            aria-hidden
            className="font-mono text-[0.6875rem] tracking-[0.12em] text-primary uppercase opacity-0 transition-opacity duration-(--animate-duration-fast) group-hover/trace:opacity-100 group-focus-visible/trace:opacity-100 [@media(hover:none)]:opacity-100"
          >
            trace
          </span>
        </span>
      </button>

      {/* The chain. `grid-rows-[0fr]` to `[1fr]` animates height without animating
          `height` itself, so this stays off the layout path. */}
      <div
        id={panelId}
        className={cn(
          "grid transition-[grid-template-rows] duration-(--animate-duration-base) ease-out",
          // No hover on touch: show the evidence rather than hiding it behind a
          // gesture the interface never advertises.
          show ? "grid-rows-[1fr]" : "grid-rows-[0fr] [@media(hover:none)]:grid-rows-[1fr]",
        )}
      >
        <div className="overflow-hidden">
          <ol className="relative mt-3 space-y-2.5 pl-5">
            {/* The line itself: one continuous rule the whole chain hangs from. */}
            <span
              aria-hidden
              className="absolute inset-y-1 left-1 w-px bg-primary/30"
            />
            {steps.map((step, i) => (
              <motion.li
                key={step.source}
                initial={armed && !reduced ? { opacity: 0, x: -4 } : false}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: reduced ? 0 : 0.3, delay: reduced ? 0 : i * 0.06 }}
                className="relative"
              >
                <span
                  aria-hidden
                  className="absolute top-1.5 -left-4 size-1.5 rounded-full bg-primary"
                />
                <p className="font-mono text-[0.6875rem] tracking-[0.12em] text-primary uppercase">
                  {step.source}
                </p>
                <p className="text-meta text-muted-foreground">{step.detail}</p>
              </motion.li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

/** A horizontal chain: source travels to conclusion, arrow by arrow.
 *
 * The other half of the signature: where `TraceEvidence` runs a conclusion backwards to
 * its sources, this runs forwards - `GitHub → Python expertise → Technical depth 91 →
 * 94% match` - and is used where the page is showing inference happening rather than
 * offering it to be inspected.
 */
export function EvidenceChain({
  steps,
  className,
}: {
  /** Each link's text. The last is treated as the conclusion and carries the accent. */
  steps: readonly string[];
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const animate = armed && !reduced;

  return (
    <ol className={cn("flex flex-wrap items-center gap-x-2 gap-y-2", className)}>
      {steps.map((step, i) => {
        const last = i === steps.length - 1;
        return (
          <motion.li
            key={step}
            className="flex items-center gap-2"
            initial={animate ? { opacity: 0 } : false}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: reduced ? 0 : 0.35, delay: animate ? i * 0.12 : 0 }}
          >
            {i > 0 ? (
              <ArrowRight aria-hidden className="size-3.5 shrink-0 text-primary/50" />
            ) : null}
            <span
              className={cn(
                "font-mono text-meta whitespace-nowrap",
                last
                  ? "rounded-sm bg-primary-muted px-2 py-1 font-medium text-primary"
                  : "text-muted-foreground",
              )}
            >
              {step}
            </span>
          </motion.li>
        );
      })}
    </ol>
  );
}

/** A hairline that draws itself between two points as the scene enters view.
 *
 * The connective tissue used inside the larger compositions - a signal reaching a core,
 * a stage reaching the next. `scaleX`/`scaleY` on a transform, so it never triggers
 * layout. Decorative by definition, so always `aria-hidden`: the relationship it draws
 * is stated in the surrounding text.
 */
export function DrawnLine({
  orientation = "horizontal",
  delay = 0,
  duration = 0.8,
  className,
}: {
  orientation?: "horizontal" | "vertical";
  delay?: number;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const vertical = orientation === "vertical";

  const base = cn(
    "block bg-primary/35",
    vertical ? "w-px origin-top" : "h-px origin-left",
    className,
  );

  if (!armed || reduced) return <span aria-hidden className={base} />;

  return (
    <motion.span
      aria-hidden
      className={base}
      initial={vertical ? { scaleY: 0 } : { scaleX: 0 }}
      whileInView={vertical ? { scaleY: 1 } : { scaleX: 1 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration, delay, ease: [0.22, 1, 0.36, 1] }}
    />
  );
}
