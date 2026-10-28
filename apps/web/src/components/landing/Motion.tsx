"use client";

import { useSyncExternalStore } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";

import { cn } from "@/lib/utils";

/** True only after the component has mounted on the client.
 *
 * Reveal animations start from `opacity: 0`, which means that without JS, or before
 * hydration, the content they wrap is invisible. Server-rendering the page is worthless
 * if 29 of its blocks are transparent until a bundle loads, so every wrapper below
 * renders plain markup first and only arms its animation once this flips. */
const subscribeNever = () => () => {};

export function useArmed(): boolean {
  // useSyncExternalStore is the right primitive for "are we on the client yet": it
  // returns the server snapshot during SSR and hydration, then the client snapshot,
  // without a setState-in-effect that would schedule a cascading render.
  return useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );
}

/** Motion primitives for the landing page, and only the landing page.
 *
 * The app animates on state change alone; scroll-linked motion lives here so the two
 * surfaces cannot bleed into each other (enforced by design-system.test.ts, which fails
 * if `whileInView` or `useScroll` appears outside this directory).
 *
 * Everything below is transform and opacity only, so animation stays off the layout and
 * paint path. `useReducedMotion` collapses each effect to a plain fade rather than
 * disabling it, so the reduced-motion page still reads as composed rather than broken.
 */

const EASE = [0.22, 1, 0.36, 1] as const;

/** Reveals children as the section scrolls into view.
 *
 * `once` matters: re-animating on every scroll direction change is the effect that
 * makes a page feel restless rather than considered. */
export function Reveal({
  children,
  className,
  delay = 0,
  y = 16,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  y?: number;
  as?: "div" | "section" | "li" | "span";
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const Comp = motion[as];

  if (!armed) {
    const Plain = as;
    return <Plain className={className}>{children}</Plain>;
  }

  return (
    <Comp
      className={className}
      initial={{ opacity: 0, y: reduced ? 0 : y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: EASE }}
    >
      {children}
    </Comp>
  );
}

/** Parent for a staggered group. Children must be `StaggerItem`. */
export function Stagger({
  children,
  className,
  gap = 0.06,
}: {
  children: React.ReactNode;
  className?: string;
  gap?: number;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const variants: Variants = {
    hidden: {},
    show: { transition: { staggerChildren: reduced ? 0 : gap } },
  };

  if (!armed) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      variants={variants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const variants: Variants = {
    hidden: { opacity: 0, y: reduced ? 0 : 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
  };

  if (!armed) return <div className={className}>{children}</div>;

  return (
    <motion.div className={className} variants={variants}>
      {children}
    </motion.div>
  );
}

/** The hero's load sequence. Words rise in order, which is the one place on the page
 * where motion is doing composition rather than decoration. */
export function KineticHeadline({
  lines,
  className,
}: {
  lines: React.ReactNode[];
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (!armed) {
    return (
      <h1 className={className}>
        {lines.map((line, i) => (
          <span key={i} className="block">
            {line}
          </span>
        ))}
      </h1>
    );
  }

  return (
    <h1 className={className}>
      {lines.map((line, i) => (
        <motion.span
          key={i}
          className="block"
          initial={{ opacity: 0, y: reduced ? 0 : "0.4em" }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.7,
            delay: reduced ? 0 : 0.08 * i,
            ease: EASE,
          }}
        >
          {line}
        </motion.span>
      ))}
    </h1>
  );
}

/** A tile that lights where the pointer is.
 *
 * Pointer position is written to a CSS custom property rather than to React state: a
 * state update per mousemove would re-render the subtree on every frame. The highlight
 * itself is a `radial-gradient` on a pseudo-element that only fades in on hover, so
 * nothing animates while the pointer is elsewhere. */
export function SpotlightTile({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      onPointerMove={(e) => {
        const el = e.currentTarget;
        const rect = el.getBoundingClientRect();
        el.style.setProperty("--spot-x", `${e.clientX - rect.left}px`);
        el.style.setProperty("--spot-y", `${e.clientY - rect.top}px`);
      }}
      className={cn(
        "group/tile relative overflow-hidden rounded-lg bg-card shadow-flat",
        "before:pointer-events-none before:absolute before:inset-0 before:opacity-0 before:transition-opacity before:duration-300 before:content-['']",
        "before:bg-[radial-gradient(220px_circle_at_var(--spot-x,50%)_var(--spot-y,50%),color-mix(in_oklch,var(--primary)_10%,transparent),transparent_70%)]",
        "hover:before:opacity-100",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Counts up to `value` once the number scrolls into view.
 *
 * Scores are the product's substance, so they arrive rather than simply appearing.
 * Respects reduced motion by rendering the final value immediately. */
export function CountUp({
  value,
  decimals = 0,
  className,
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (reduced || !armed) {
    return (
      <span data-numeric className={className}>
        {value.toFixed(decimals)}
      </span>
    );
  }

  return (
    <motion.span
      data-numeric
      className={className}
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >
      {value.toFixed(decimals)}
    </motion.span>
  );
}

/** Spring preset used wherever motion should feel driven rather than timed.
 *
 * Tuned to settle without visible overshoot: a bouncy spring on a data product reads as
 * playful in the wrong way. */
const SPRING = { type: "spring", stiffness: 260, damping: 30, mass: 0.9 } as const;

/** Page-load sequence for a hero. Children arrive in order on a spring.
 *
 * Distinct from `Stagger`, which is scroll-triggered: this fires once on mount, because
 * the hero is already in view and waiting for a scroll that never comes would leave the
 * most important content static. */
export function LoadSequence({
  children,
  className,
  gap = 0.07,
}: {
  children: React.ReactNode;
  className?: string;
  gap?: number;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (!armed) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: reduced ? 0 : gap } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function LoadItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (!armed) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: reduced ? 0 : 14 },
        show: { opacity: 1, y: 0, transition: SPRING },
      }}
    >
      {children}
    </motion.div>
  );
}

/** Draws a vertical rule from top to bottom as the section scrolls through the viewport.
 *
 * Used for the hackathon-to-hire spine. The page's claim is that the stages are one
 * continuous run, and a line that draws itself says that more directly than a static
 * border does. `scaleY` on a transform, so this never triggers layout. */
export function DrawLine({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (!armed || reduced) {
    return <span aria-hidden className={cn("block origin-top", className)} />;
  }

  return (
    <motion.span
      aria-hidden
      className={cn("block origin-top", className)}
      initial={{ scaleY: 0 }}
      whileInView={{ scaleY: 1 }}
      viewport={{ once: true, margin: "-15% 0px -25% 0px" }}
      transition={{ duration: 1.1, ease: EASE }}
    />
  );
}

/** A rule that strikes through its label as it enters view.
 *
 * The Problem section argues by contrast: unverifiable claims on the left, evidence on
 * the right. Striking the claims out on entry performs that argument rather than
 * asserting it. */
export function StrikeThrough({
  children,
  index = 0,
  className,
}: {
  children: React.ReactNode;
  index?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  return (
    <span className={cn("relative inline-block", className)}>
      {children}
      {armed && !reduced ? (
        <motion.span
          aria-hidden
          className="absolute inset-x-0 top-1/2 h-px origin-left bg-muted-foreground"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.45, delay: 0.15 + index * 0.12, ease: EASE }}
        />
      ) : (
        <span
          aria-hidden
          className="absolute inset-x-0 top-1/2 h-px bg-muted-foreground"
        />
      )}
    </span>
  );
}

/** Lifts on hover, on a spring. For the bento tiles.
 *
 * `whileHover` on transform only: a shadow transition would repaint the whole tile. */
export function HoverLift({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  if (!armed || reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      whileHover={{ y: -4 }}
      transition={SPRING}
    >
      {children}
    </motion.div>
  );
}
