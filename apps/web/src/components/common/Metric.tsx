import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface MetricProps {
  label: string;
  /** Pre-formatted. Numbers render with tabular figures so columns of these align. */
  value: React.ReactNode;
  /** One line of context — a comparison, a period, a caveat. */
  hint?: string;
  icon?: LucideIcon;
  href?: string;
  className?: string;
}

/** A single number with its label.
 *
 * Deliberately plain: no coloured background, no oversized figure. A grid of tinted
 * KPI tiles competes with itself and makes every number look equally important. */
export function Metric({
  label,
  value,
  hint,
  icon: Icon,
  href,
  className,
}: MetricProps) {
  const body = (
    <>
      <div className="flex items-center gap-1.5">
        {Icon ? (
          <Icon aria-hidden className="size-3.5 text-muted-foreground" />
        ) : null}
        <span className="text-meta text-muted-foreground">{label}</span>
      </div>
      <div
        data-numeric
        className="text-title font-medium tabular-nums text-foreground"
      >
        {value}
      </div>
      {hint ? <p className="text-meta text-muted-foreground">{hint}</p> : null}
    </>
  );

  const base = "flex flex-col gap-1 rounded-lg bg-card px-4 py-3 shadow-flat";

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          base,
          "outline-none transition-shadow duration-(--animate-duration-fast) hover:shadow-raised focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        )}
      >
        {body}
      </Link>
    );
  }

  return <div className={cn(base, className)}>{body}</div>;
}

/** Responsive row of metrics. */
export function MetricGrid({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 lg:grid-cols-4", className)}>
      {children}
    </div>
  );
}
