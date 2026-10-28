"use client";

import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";

/** The agent system, drawn as signals converging on a core.
 *
 * A grid of six "AI agent" cards is the default way to render this and says nothing
 * about how the system works. Here the six agents sit on a ring, each connected to the
 * centre by a line that pulses inward, because the actual architecture is a supervisor
 * fanning work out to subgraphs and merging what they return.
 *
 * Inline SVG rather than DOM nodes: the connecting lines have to be drawn, and one
 * `<svg>` is far cheaper than eighteen absolutely-positioned divs.
 */

const AGENTS = [
  "Talent intelligence",
  "Verification",
  "Interview",
  "Recruitment",
  "Presentation",
  "Trust",
] as const;

const SIZE = 420;
const CENTER = SIZE / 2;
const RADIUS = 150;

export function AgentOrbit() {
  const reduced = useReducedMotion();
  const gradientId = useId();

  const nodes = AGENTS.map((label, i) => {
    // Start at -90deg so the first agent sits at the top rather than at 3 o'clock.
    const angle = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2;
    return {
      label,
      x: CENTER + Math.cos(angle) * RADIUS,
      y: CENTER + Math.sin(angle) * RADIUS,
    };
  });

  return (
    <div className="relative mx-auto w-full max-w-[420px]">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label="Six agents feeding a central talent profile: talent intelligence, verification, interview, recruitment, presentation and trust."
      >
        <defs>
          <radialGradient id={gradientId}>
            <stop
              offset="0%"
              stopColor="var(--primary)"
              stopOpacity={0.18}
            />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
          </radialGradient>
        </defs>

        {/* Soft field behind the core, so the centre reads as the destination. */}
        <circle cx={CENTER} cy={CENTER} r={110} fill={`url(#${gradientId})`} />

        {/* The ring the agents sit on. */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke="var(--border)"
          strokeDasharray="3 6"
        />

        {nodes.map((n, i) => (
          <g key={n.label}>
            <line
              x1={n.x}
              y1={n.y}
              x2={CENTER}
              y2={CENTER}
              stroke="var(--border)"
              strokeWidth={1}
            />
            {/* A dot travelling the line: evidence moving from agent to profile. */}
            {!reduced ? (
              <motion.circle
                r={2.5}
                fill="var(--primary)"
                initial={{ cx: n.x, cy: n.y, opacity: 0 }}
                animate={{
                  cx: [n.x, CENTER],
                  cy: [n.y, CENTER],
                  opacity: [0, 1, 1, 0],
                }}
                transition={{
                  duration: 2.4,
                  repeat: Infinity,
                  delay: i * 0.4,
                  ease: "easeInOut",
                }}
              />
            ) : null}
            <circle
              cx={n.x}
              cy={n.y}
              r={5}
              fill="var(--background)"
              stroke="var(--primary)"
              strokeWidth={1.5}
            />
          </g>
        ))}

        {/* The core. */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={44}
          fill="var(--card)"
          stroke="var(--border)"
        />
        <text
          x={CENTER}
          y={CENTER - 4}
          textAnchor="middle"
          className="fill-foreground"
          style={{ fontSize: 13, fontWeight: 600 }}
        >
          Talent
        </text>
        <text
          x={CENTER}
          y={CENTER + 12}
          textAnchor="middle"
          className="fill-foreground"
          style={{ fontSize: 13, fontWeight: 600 }}
        >
          profile
        </text>
      </svg>

      {/* Labels live in the DOM rather than as SVG <text>, so they inherit the page
          font and stay selectable and translatable. */}
      <ul className="pointer-events-none absolute inset-0">
        {nodes.map((n) => (
          <li
            key={n.label}
            className="absolute -translate-x-1/2 whitespace-nowrap text-meta text-muted-foreground"
            style={{
              left: `${(n.x / SIZE) * 100}%`,
              top: `${(n.y / SIZE) * 100}%`,
              transform: `translate(-50%, ${n.y < CENTER ? "-160%" : "60%"})`,
            }}
          >
            {n.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
