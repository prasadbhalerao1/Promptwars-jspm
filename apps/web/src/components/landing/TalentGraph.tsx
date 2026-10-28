"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { useArmed } from "@/components/landing/Motion";

/** Signature moment 05: a recruiter query reshaping the talent graph.
 *
 * The recruiter story is "describe a role in plain language and read why each candidate
 * fits". A search box above a results table states that; this shows it. A field of
 * candidates sits mostly dormant, a query runs, the clusters it cares about illuminate,
 * and one candidate resolves with the evidence route that earned the match.
 *
 * Data-dense on purpose. A handful of circles reads as a diagram of a system with six
 * users; a field of 120 reads as a talent graph. They are cheap - one `<circle>` each,
 * no per-node React state, and the whole field is inert SVG until a query runs.
 */

const VB = { w: 1200, h: 620 };

/** Clusters, hand-placed. A force simulation would cost a dependency and give worse
 * control over how the composition actually reads. */
const CLUSTERS = [
  { id: "genai", label: "GenAI", cx: 300, cy: 190, r: 118 },
  { id: "python", label: "Python", cx: 560, cy: 380, r: 132 },
  { id: "frontend", label: "Frontend", cx: 250, cy: 460, r: 104 },
  { id: "systems", label: "Systems", cx: 830, cy: 200, r: 110 },
  { id: "oss", label: "Open source", cx: 880, cy: 470, r: 112 },
] as const;

type ClusterId = (typeof CLUSTERS)[number]["id"];

/** The queries that cycle. Each lights a different set of clusters, which is what makes
 * the graph read as responding rather than replaying one canned animation. */
const QUERIES: readonly {
  text: string;
  clusters: readonly ClusterId[];
  match: number;
  route: readonly string[];
}[] = [
  {
    text: "GenAI engineers with open-source experience",
    clusters: ["genai", "python", "oss"],
    match: 94,
    route: ["GitHub", "4 GenAI projects", "47 OSS contributions", "Verified"],
  },
  {
    text: "Senior backend, verified Python, hackathon record",
    clusters: ["python", "systems"],
    match: 91,
    route: ["Assessment 93rd", "12 repositories", "3 hackathons", "Verified"],
  },
  {
    text: "Frontend engineers who ship production work",
    clusters: ["frontend", "oss"],
    match: 88,
    route: ["1,284 commits", "3 in production", "Reviewed", "Verified"],
  },
] as const;

/** Processing states shown while the query runs. Elegant text beats a spinner, and each
 * line names something the system genuinely does. */
const STAGES = [
  "Understanding role",
  "Searching talent graph",
  "Evaluating project relevance",
  "Checking verification",
  "Ranking candidates",
] as const;

/** Deterministic pseudo-random, so the field is identical on server and client.
 * `Math.random()` here would hydrate to a different layout every load and produce a
 * mismatch warning. */
function seeded(i: number, salt: number) {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

type Node = {
  x: number;
  y: number;
  r: number;
  /** Part of the reduced field drawn on phones. */
  onPhone: boolean;
  cluster: ClusterId;
};

const STAGE_MS = 520;
const RESOLVE_AT = STAGE_MS * STAGES.length;
const CYCLE = RESOLVE_AT + 4200;

export function TalentGraph({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const armed = useArmed();
  const ref = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [tick, setTick] = useState(0);
  const [queryIndex, setQueryIndex] = useState(0);
  /** Laptop and phone get different compositions, not one scaled between them. Starts
   * `false` so the server renders the simpler phone field and the laptop upgrades after
   * mount - the reverse would ship a 110-node SVG to every phone. */
  const [wide, setWide] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 64rem)");
    const sync = () => setWide(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  /** The candidate field. Most nodes sit in a cluster; a scattering sits between them,
   * because a graph where every point belongs to a tidy group looks synthetic.
   *
   * The phone gets a genuinely different field rather than the same one shrunk: far fewer
   * nodes, drawn larger, so it still reads as a talent graph instead of as grey dust. */
  const nodes = useMemo<Node[]>(() => {
    const out: Node[] = [];
    CLUSTERS.forEach((cluster, ci) => {
      for (let i = 0; i < 22; i++) {
        const a = seeded(i, ci) * Math.PI * 2;
        // sqrt keeps the distribution even rather than crowding the centre.
        const d = Math.sqrt(seeded(i, ci + 40)) * cluster.r;
        out.push({
          x: Math.round((cluster.cx + Math.cos(a) * d) * 100) / 100,
          y: Math.round((cluster.cy + Math.sin(a) * d) * 100) / 100,
          r: Math.round((1.6 + seeded(i, ci + 80) * 1.8) * 100) / 100,
          // The phone shows a readable subset rather than the full field: 110 dots at
          // 390px is grey dust, not a talent graph.
          onPhone: i < 5,
          cluster: cluster.id,
        });
      }
    });
    return out;
  }, []);

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
    const TICKS = Math.round(CYCLE / STAGE_MS);
    let t = 0;
    const timer = setInterval(() => {
      t = (t + 1) % TICKS;
      setTick(t);
      if (t === 0) setQueryIndex((q) => (q + 1) % QUERIES.length);
    }, STAGE_MS);
    return () => clearInterval(timer);
  }, [animating]);

  const query = QUERIES[queryIndex];
  // With motion off the graph shows a resolved query rather than a dormant field: the
  // point is the response, and a static field of grey dots says nothing.
  const stage = animating ? Math.min(tick, STAGES.length) : STAGES.length;
  const resolved = stage >= STAGES.length;
  const active = new Set<ClusterId>(query.clusters);

  return (
    <div ref={ref} className={cn("relative", className)}>
      {/* The query, as an instrument readout rather than a fake input someone might try
          to type into. */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 pb-5">
        <p className="min-w-0 text-lead text-foreground">
          <span className="text-muted-foreground">Query </span>
          &ldquo;{query.text}&rdquo;
        </p>
        <p
          aria-live="polite"
          className="font-mono text-meta tracking-[0.12em] text-muted-foreground uppercase"
        >
          {resolved ? `${query.match}% top match` : STAGES[stage]}
        </p>
      </div>

      <svg
        // Phones get a tighter crop around the active clusters; the laptop sees the whole
        // field. Same drawing, framed for the screen it is on.
        viewBox={wide ? `0 0 ${VB.w} ${VB.h}` : "150 90 820 520"}
        // Taller crop on small screens: the clusters stay legible as a field even when
        // the labels inside are too small to read, and the match is restated as text
        // below rather than relying on the 10px SVG type.
        className="h-[300px] w-full lg:h-auto"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`A talent graph of candidates clustered by GenAI, Python, frontend, systems and open source. The query "${query.text}" illuminates the relevant clusters and resolves a top match at ${query.match} percent.`}
      >
        {/* Cluster fields. Faint by default; the query's clusters warm. */}
        {CLUSTERS.map((c) => {
          const lit = active.has(c.id) && stage >= 2;
          return (
            <motion.circle
              key={c.id}
              cx={c.cx}
              cy={c.cy}
              r={c.r}
              initial={false}
              animate={{ opacity: lit ? 1 : 0.35 }}
              transition={{ duration: reduced ? 0 : 0.6 }}
              fill={lit ? "var(--primary-muted)" : "transparent"}
              stroke="var(--border)"
              strokeDasharray="3 5"
            />
          );
        })}

        {/* The candidates. */}
        {nodes.map((n, i) => {
          const lit = active.has(n.cluster) && stage >= 2;
          return (
            <motion.circle
              key={i}
              // Visibility in CSS so the laptop's full field is correct without JS.
              // The phone's larger radius rides on `wide` instead: animating the SVG `r`
              // geometry attribute through a custom property is not reliably supported,
              // and if the flag never resolves the phone simply shows the smaller subset.
              className={n.onPhone ? undefined : "invisible lg:visible"}
              cx={n.x}
              cy={n.y}
              r={!wide && n.onPhone ? n.r * 2.4 : n.r}
              fill={lit ? "var(--primary)" : "var(--muted-foreground)"}
              initial={false}
              animate={{ opacity: lit ? 0.85 : 0.16 }}
              transition={{
                duration: reduced ? 0 : 0.5,
                delay: reduced || !lit ? 0 : (i % 22) * 0.012,
              }}
            />
          );
        })}

        {CLUSTERS.map((c) => (
          <text
            key={`${c.id}-label`}
            x={c.cx}
            y={c.cy - c.r - 12}
            textAnchor="middle"
            className={cn(
              "font-mono font-medium",
              // Scaled up on phones because the viewBox crop magnifies far less than the
              // width reduction shrinks: at the laptop size these would be ~4px.
              wide ? "text-[12px]" : "text-[19px]",
              active.has(c.id) && stage >= 2
                ? "fill-primary"
                : "fill-muted-foreground",
            )}
          >
            {c.label}
          </text>
        ))}

        {/* The resolved candidate, and the evidence route that produced the match.
            Desktop only: at mobile widths this card renders around 8px and is restated
            as readable text beneath the graph instead. */}
        <motion.g
          // `visibility` rather than a React flag: driven purely by CSS, this needs no
          // hydration and cannot disagree between server and client the way a state
          // default does. SVG honours `visibility` where it ignores `display:block`.
          className="invisible lg:visible"
          initial={false}
          animate={{ opacity: resolved ? 1 : 0 }}
          transition={{ duration: reduced ? 0 : 0.5 }}
        >
          <line
            x1={560}
            y1={380}
            x2={980}
            y2={110}
            stroke="var(--primary)"
            strokeWidth={1.5}
            strokeOpacity={0.5}
          />
          <circle cx={560} cy={380} r={7} fill="var(--primary)" />
          <rect
            x={980}
            y={44}
            width={188}
            height={132}
            rx={12}
            fill="var(--card)"
            stroke="var(--primary)"
            strokeOpacity={0.35}
          />
          <text
            x={1000}
            y={74}
            className="fill-muted-foreground font-mono text-[10.5px] tracking-[0.14em]"
          >
            TOP MATCH
          </text>
          <text x={1000} y={104} className="fill-foreground text-[15px] font-medium">
            Alice Chen
          </text>
          <text
            x={1000}
            y={140}
            className="fill-foreground font-mono text-[30px] font-medium"
          >
            {query.match}%
          </text>
          <text
            x={1000}
            y={162}
            className="fill-success font-mono text-[10.5px] tracking-[0.14em]"
          >
            EVIDENCE VERIFIED
          </text>
        </motion.g>
      </svg>

      {/* The match, restated for small screens where the in-graph card is too small to
          read. Hidden on desktop, where the card in the SVG already says it. */}
      <motion.div
        className="mt-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 lg:hidden"
        initial={false}
        animate={{ opacity: resolved ? 1 : 0 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
      >
        <span className="font-mono text-meta tracking-[0.12em] text-muted-foreground uppercase">
          Top match
        </span>
        <span className="text-section font-medium text-foreground">Alice Chen</span>
        <span
          data-numeric
          className="font-mono text-section font-medium text-primary"
        >
          {query.match}%
        </span>
      </motion.div>

      {/* The route, in text, so the match is explainable rather than asserted - and so
          the information is available to a screen reader as content, not as a graphic. */}
      <motion.ol
        className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2"
        initial={false}
        animate={{ opacity: resolved ? 1 : 0 }}
        transition={{ duration: reduced ? 0 : 0.4 }}
      >
        {query.route.map((step, i) => (
          <li key={step} className="flex items-center gap-2">
            {i > 0 ? (
              <span aria-hidden className="h-px w-4 bg-primary/40" />
            ) : null}
            <span
              className={cn(
                "font-mono text-meta whitespace-nowrap",
                i === query.route.length - 1
                  ? "rounded-sm bg-primary-muted px-2 py-1 font-medium text-primary"
                  : "text-muted-foreground",
              )}
            >
              {step}
            </span>
          </li>
        ))}
      </motion.ol>
    </div>
  );
}
