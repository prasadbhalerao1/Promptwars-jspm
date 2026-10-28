"use client";

import { useEffect, useRef, useState } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Background and depth layers for the landing page.
 *
 * These are decorative and sit behind content at negative z-index, so they never
 * intercept a pointer event or a screen reader. Everything animates on transform and
 * opacity only, and each effect degrades to a static state under
 * `prefers-reduced-motion`.
 */

/** Engineering grid that fades toward the edges.
 *
 * Two layered gradients rather than an SVG pattern: the mask is what keeps a grid from
 * reading as graph paper, and CSS does the fade far more cheaply than a tiled image. */
export function GridField({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 -z-10 overflow-hidden",
        className,
      )}
    >
      <div
        className="absolute inset-0 opacity-[0.55]"
        style={{
          backgroundImage:
            "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage:
            "radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%)",
        }}
      />
    </div>
  );
}

/** A card that tilts slightly toward the pointer.
 *
 * Rotation is written straight to the element's transform rather than through React
 * state, so a pointer move costs one style write instead of a re-render per frame. */
export function TiltCard({
  children,
  className,
  max = 6,
}: {
  children: React.ReactNode;
  className?: string;
  max?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  return (
    <div
      ref={ref}
      onPointerMove={(e) => {
        if (reduced || !ref.current) return;
        const r = ref.current.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        ref.current.style.transform = `perspective(1200px) rotateY(${px * max}deg) rotateX(${-py * max}deg)`;
      }}
      onPointerLeave={() => {
        if (ref.current) {
          ref.current.style.transform =
            "perspective(1200px) rotateY(0deg) rotateX(0deg)";
        }
      }}
      className={cn("transition-transform duration-300 ease-out", className)}
      style={{ transformStyle: "preserve-3d" }}
    >
      {children}
    </div>
  );
}

/** A line of text that types itself out, then swaps to the next one.
 *
 * Used for the recruiter search demo, where watching the query being written is what
 * makes the search feel like a live product rather than a screenshot. */
export function TypingText({
  phrases,
  className,
  onPhraseChange,
}: {
  phrases: readonly string[];
  className?: string;
  onPhraseChange?: (index: number) => void;
}) {
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [text, setText] = useState(reduced ? phrases[0] : "");

  useEffect(() => {
    if (reduced) return;
    const full = phrases[index];
    let char = 0;
    let hold: ReturnType<typeof setTimeout>;

    const tick = setInterval(() => {
      char += 1;
      setText(full.slice(0, char));
      if (char >= full.length) {
        clearInterval(tick);
        hold = setTimeout(() => {
          const next = (index + 1) % phrases.length;
          setIndex(next);
          onPhraseChange?.(next);
        }, 2600);
      }
    }, 32);

    return () => {
      clearInterval(tick);
      clearTimeout(hold);
    };
  }, [index, phrases, reduced, onPhraseChange]);

  return (
    <span className={className}>
      {text}
      {!reduced ? (
        <span className="ml-0.5 inline-block h-[1em] w-px translate-y-0.5 animate-pulse bg-primary align-middle" />
      ) : null}
    </span>
  );
}

/** Numbers that count up when scrolled into view. */
export function Counter({
  to,
  decimals = 0,
  duration = 1100,
  className,
}: {
  to: number;
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const [value, setValue] = useState(to);
  const running = useRef(false);

  /** Runs the count. Driven by framer-motion's own viewport handling rather than a
   * hand-rolled IntersectionObserver: the bespoke version left these figures stuck at
   * `0` on the rendered page, because it attached before layout and its `done` latch
   * then blocked every retry. On a page arguing that every number carries evidence, a
   * stuck zero reads as real data reporting "nothing found", so this must not be
   * clever. */
  const start = () => {
    if (running.current || reduced) return;
    running.current = true;
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      // easeOutCubic: fast arrival, gentle settle, so the number lands rather
      // than creeping.
      setValue(to * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  // Server, pre-hydration and reduced-motion all render the final value, so the figure
  // is correct even if the animation never runs.
  if (!armed || reduced) {
    return (
      <span data-numeric className={className}>
        {to.toFixed(decimals)}
      </span>
    );
  }

  return (
    <motion.span
      data-numeric
      className={className}
      initial={{ opacity: 1 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: "-60px" }}
      onViewportEnter={start}
    >
      {value.toFixed(decimals)}
    </motion.span>
  );
}

/** Scroll progress across the whole page.
 *
 * This is information, not decoration: the landing page is nine sections long and a
 * reader benefits from knowing how much is left. `useScroll` drives `scaleX` directly
 * through a motion value, so progress never passes through React state and costs no
 * re-render per frame. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 180,
    damping: 30,
    restDelta: 0.001,
  });
  const reduced = useReducedMotion();

  if (reduced) return null;

  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed inset-x-0 top-0 z-50 h-0.5 origin-left bg-primary"
    />
  );
}

/** Moves its children at a different rate to the page as it scrolls.
 *
 * Used once, on the hero's product card, to place the product on a different plane from
 * the pitch beside it. `useTransform` on a scroll motion value means the offset is
 * written straight to the transform, so this is a compositor-only effect. */
export function Parallax({
  children,
  distance = 40,
  className,
}: {
  children: React.ReactNode;
  distance?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [distance, -distance]);

  return (
    <div ref={ref} className={className}>
      <motion.div style={reduced ? undefined : { y }}>{children}</motion.div>
    </div>
  );
}
