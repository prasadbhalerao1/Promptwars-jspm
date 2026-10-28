"use client";

import { cn } from "@/lib/utils";

/** Shared chart chrome.
 *
 * Every chart previously hand-rolled its own tooltip. Three different treatments
 * coexisted (`border bg-card shadow-lg`, an inline `var(--shadow-overlay)` style, and a
 * Recharts default), which is what made the charts read as separately built. These are
 * the single definitions; charts import them rather than restyling a div.
 */

/** Axis tick styling, spread into a Recharts `tick` prop.
 *
 * Recharts renders ticks as SVG `<text>`, which does not inherit the page font, so the
 * face and size have to be passed explicitly rather than set with a class. */
export const CHART_TICK = {
  fill: "var(--muted-foreground)",
  fontSize: 11,
  fontFamily: "var(--font-sans)",
} as const;

export const CHART_GRID = {
  stroke: "var(--border)",
  strokeDasharray: "2 4",
} as const;

/** Cursor shown behind the hovered point. Subtle enough not to compete with the mark. */
export const CHART_CURSOR = {
  fill: "var(--primary)",
  fillOpacity: 0.06,
} as const;

export interface ChartTooltipRow {
  label: string;
  value: string;
  /** A CSS colour for the series swatch. Omitted rows render without one. */
  color?: string;
}

/** The one tooltip body. `title` is the category (a date, a label); rows are the
 * series values, already formatted by the caller so this stays presentational. */
export function ChartTooltipContent({
  title,
  rows,
  className,
}: {
  title?: string;
  rows: ChartTooltipRow[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "min-w-[9rem] rounded-md bg-popover p-2.5 shadow-overlay",
        className,
      )}
    >
      {title ? (
        <p className="text-meta font-medium text-muted-foreground">{title}</p>
      ) : null}
      <div className={cn("space-y-0.5", title && "mt-1.5")}>
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-4"
          >
            <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
              {row.color ? (
                <span
                  aria-hidden
                  className="size-2 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: row.color }}
                />
              ) : null}
              {row.label}
            </span>
            <span
              data-numeric
              className="font-mono text-meta font-medium text-foreground"
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Fixed-height chart frame. Recharts' `ResponsiveContainer` needs a sized parent, and
 * giving it one here means the height is reserved before data lands, so a chart cannot
 * shift the page as it loads. */
export function ChartFrame({
  height = 224,
  className,
  children,
}: {
  height?: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("w-full", className)} style={{ height }}>
      {children}
    </div>
  );
}
