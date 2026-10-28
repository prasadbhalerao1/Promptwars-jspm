"use client";

import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Raw signals resolving through a processing layer into one profile.
 *
 * Drawn rather than described. The claim TRACE makes is that scattered, unrelated
 * evidence resolves into a single accountable figure, and a row of feature cards says
 * nothing about how the pieces relate. An SVG where lines actually travel from source to
 * core says it in one glance.
 *
 * Pure SVG and framer-motion — no graph library. The layout is fixed and hand-placed, so
 * a force simulation would cost a dependency and give worse control over composition.
 */

const VB = { w: 900, h: 424 };

/** Left column: the raw inputs. `y` positions are hand-tuned rather than distributed
 * evenly, so the column reads as composed instead of as a list. */
const SOURCES = [
  { label: "Commit history", detail: "1,284", y: 52 },
  { label: "Repositories", detail: "12", y: 132 },
  { label: "Hackathons", detail: "3", y: 212 },
  { label: "Certificates", detail: "2", y: 292 },
  { label: "Assessments", detail: "4", y: 372 },
] as const;

/** Middle column: what reads them. */
const AGENTS = [
  { label: "Talent intelligence", y: 118 },
  { label: "Verification", y: 230 },
  { label: "Trust", y: 342 },
] as const;

/** Which source feeds which agent. Deliberately not a full mesh: the point is that
 * different evidence answers different questions. */
const EDGES: readonly (readonly [number, number])[] = [
  [0, 0],
  [1, 0],
  [2, 0],
  [2, 1],
  [3, 1],
  [4, 1],
  [3, 2],
  [4, 2],
  [0, 2],
] as const;

const SRC_X = 236;
const AGENT_X = 470;
const CORE_X = 706;
const CORE_Y = 230;

/** Cubic between two points, flattened horizontally so lines leave and arrive level.
 * A straight line here would read as a wiring diagram; the curve is what makes it read
 * as flow. */
function curve(x1: number, y1: number, x2: number, y2: number) {
  const mid = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
}

export function SignalGraph({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();

  // `whileInView` rather than a hand-rolled IntersectionObserver. An observer attached
  // to the wrapper never fired here — the element had not laid out when the effect ran —
  // and left the whole diagram at opacity 0, which is exactly the class of bug a
  // rendered-page check exists to catch. framer-motion's own viewport handling is also
  // what every other animated block on this page already uses.
  const draw = armed && !reduced;

  /** Shared viewport config: `once` so the diagram settles rather than redrawing on
   * every scroll reversal, and a negative margin so it starts as it comes into view. */
  const viewport = { once: true, margin: "-80px" } as const;

  /** With motion off — no JS, or reduced motion — the diagram must render complete.
   * It is a diagram first and an animation second. */
  const fade = (delay: number) =>
    draw
      ? {
          initial: { opacity: 0 },
          whileInView: { opacity: 1 },
          viewport,
          transition: { duration: 0.4, delay },
        }
      : { initial: false as const, animate: { opacity: 1 } };

  const path = (delay: number, duration: number) =>
    draw
      ? {
          initial: { pathLength: 0 },
          whileInView: { pathLength: 1 },
          viewport,
          transition: { duration, delay, ease: [0.22, 1, 0.36, 1] as const },
        }
      : { initial: false as const, animate: { pathLength: 1 } };

  return (
    <div className={cn("mx-auto w-full max-w-5xl", className)}>
      <svg
        viewBox={`0 0 ${VB.w} ${VB.h}`}
        className="h-auto w-full"
        role="img"
        aria-label="Commit history, repositories, hackathons, certificates and assessments feeding the talent intelligence, verification and trust agents, which resolve into a single verified profile scoring 82.4."
      >
        {/* Edges first so nodes paint over their endpoints. */}
        <g fill="none" strokeWidth={1.25}>
          {EDGES.map(([s, a], i) => {
            const d = curve(SRC_X, SOURCES[s].y, AGENT_X - 92, AGENTS[a].y);
            return (
              <motion.path
                key={`e-${s}-${a}`}
                d={d}
                stroke="var(--border)"
                {...path(i * 0.07, 0.9)}
              />
            );
          })}

          {/* Agent-to-core edges carry the accent: this is where inference becomes a
              score, and it should be the one coloured thing in the diagram. */}
          {AGENTS.map((agent, i) => (
            <motion.path
              key={`c-${agent.label}`}
              d={curve(AGENT_X + 92, agent.y, CORE_X - 58, CORE_Y)}
              stroke="var(--primary)"
              strokeOpacity={0.4}
              {...path(0.8 + i * 0.1, 0.8)}
            />
          ))}
        </g>

        {/* Pulses travelling agent-to-core. The only looping element, and only when
            motion is allowed — this is the diagram saying it is live. */}
        {draw
          ? AGENTS.map((agent, i) => (
              <circle key={`p-${agent.label}`} r={3} fill="var(--primary)">
                <animateMotion
                  dur="2.4s"
                  begin={`${1.6 + i * 0.5}s`}
                  repeatCount="indefinite"
                  path={curve(AGENT_X + 92, agent.y, CORE_X - 58, CORE_Y)}
                />
                <animate
                  attributeName="opacity"
                  values="0;1;1;0"
                  dur="2.4s"
                  begin={`${1.6 + i * 0.5}s`}
                  repeatCount="indefinite"
                />
              </circle>
            ))
          : null}

        {/* Sources. */}
        {SOURCES.map((s, i) => (
          <motion.g key={s.label} {...fade(i * 0.07)}>
            <rect
              x={28}
              y={s.y - 21}
              width={208}
              height={42}
              rx={8}
              fill="var(--card)"
              stroke="var(--border)"
            />
            <text
              x={44}
              y={s.y + 1}
              className="fill-foreground text-[13px] font-medium"
              dominantBaseline="middle"
            >
              {s.label}
            </text>
            <text
              x={220}
              y={s.y + 1}
              textAnchor="end"
              className="fill-muted-foreground font-mono text-[12px]"
              dominantBaseline="middle"
            >
              {s.detail}
            </text>
          </motion.g>
        ))}

        {/* Agents. */}
        {AGENTS.map((a, i) => (
          <motion.g key={a.label} {...fade(0.7 + i * 0.1)}>
            <rect
              x={AGENT_X - 92}
              y={a.y - 20}
              width={184}
              height={40}
              rx={20}
              fill="var(--primary-muted)"
              stroke="var(--primary)"
              strokeOpacity={0.28}
            />
            <text
              x={AGENT_X}
              y={a.y + 1}
              textAnchor="middle"
              className="fill-primary text-[12.5px] font-medium"
              dominantBaseline="middle"
            >
              {a.label}
            </text>
          </motion.g>
        ))}

        {/* The core: one profile, one score. */}
        <motion.g {...fade(1.5)}>
          <rect
            x={CORE_X - 58}
            y={CORE_Y - 74}
            width={172}
            height={148}
            rx={14}
            fill="var(--card)"
            stroke="var(--primary)"
            strokeOpacity={0.35}
          />
          <text
            x={CORE_X + 28}
            y={CORE_Y - 44}
            textAnchor="middle"
            className="fill-muted-foreground font-mono text-[10.5px] tracking-[0.14em]"
          >
            TALENT SCORE
          </text>
          <text
            x={CORE_X + 28}
            y={CORE_Y + 6}
            textAnchor="middle"
            className="fill-foreground font-mono text-[44px] font-medium"
          >
            82.4
          </text>
          <text
            x={CORE_X + 28}
            y={CORE_Y + 40}
            textAnchor="middle"
            className="fill-success text-[12px] font-medium"
          >
            Verified profile
          </text>
        </motion.g>
      </svg>
    </div>
  );
}
