"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

interface DataRowProps {
  /** Primary identifier for the row. */
  title: React.ReactNode;
  /** One line of context under the title — kept to one line by design; rows that need
   * more than this want a detail page, not a taller row. */
  subtitle?: React.ReactNode;
  /** Status badges, metrics, timestamps — right-aligned, wrapping under on mobile. */
  meta?: React.ReactNode;
  /** Buttons or links. Rendered after `meta`. */
  actions?: React.ReactNode;
  /** Makes the whole row a link. Prefer this over an "Open →" anchor: the entire row
   * becomes one large target instead of a small one. */
  href?: string;
  className?: string;
}

const ROW_BASE =
  "flex flex-col gap-3 rounded-md bg-card px-4 py-3 text-left shadow-flat sm:flex-row sm:items-center sm:justify-between";

/** One record in a list.
 *
 * Replaces a 160-character className that was copy-pasted across five route groups at
 * `rounded-md` + `border` + `shadow-flat` — visibly mismatched against the `Card` it was
 * usually nested inside, which uses `rounded-xl` + a ring and no shadow. */
export function DataRow({
  title,
  subtitle,
  meta,
  actions,
  href,
  className,
}: DataRowProps) {
  const content = (
    <>
      <div className="min-w-0 space-y-0.5">
        <div className="truncate text-body font-medium text-foreground">
          {title}
        </div>
        {subtitle ? (
          <div className="truncate text-meta text-muted-foreground">
            {subtitle}
          </div>
        ) : null}
      </div>
      {meta || actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {meta}
          {actions}
        </div>
      ) : null}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          ROW_BASE,
          "outline-none transition-shadow duration-(--animate-duration-fast) hover:shadow-raised focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        )}
      >
        {content}
      </Link>
    );
  }

  return <div className={cn(ROW_BASE, className)}>{content}</div>;
}

/** Vertical stack of `DataRow`s with consistent spacing. */
export function DataRowList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
}
