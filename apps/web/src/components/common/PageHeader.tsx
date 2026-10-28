import { cn } from "@/lib/utils";

interface PageProps {
  children: React.ReactNode;
  /** `reading` narrows to 720px for forms and prose; `wide` removes the cap for boards
   * and dense tables. Default is the 1200px workspace width. */
  width?: "workspace" | "reading" | "wide";
  className?: string;
}

/** Standard page container. Owns the content width and page padding so individual
 * pages stop hand-rolling `mx-auto max-w-*` — there were eight different values. */
export function Page({ children, width = "workspace", className }: PageProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full px-4 py-6 md:px-8 md:py-8",
        width === "workspace" && "max-w-workspace",
        width === "reading" && "max-w-reading",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Primary/secondary actions, right-aligned on desktop and wrapping below on mobile. */
  actions?: React.ReactNode;
  /** Rendered above the title — typically a `<Breadcrumb>` back to the parent record. */
  breadcrumb?: React.ReactNode;
  className?: string;
}

/** Page title block. Replaces 30 byte-identical hand-written `h1` strings, which is
 * also why page titles previously drifted in size and typeface between route groups. */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("mb-6 flex flex-col gap-3", className)}>
      {breadcrumb}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className="text-title font-semibold text-foreground">{title}</h1>
          {description ? (
            <p className="max-w-reading text-body text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}

/** Section heading inside a page. One level below `PageHeader`, used to group content
 * without wrapping every group in a Card. */
export function SectionHeader({
  title,
  description,
  actions,
  className,
}: Omit<PageHeaderProps, "breadcrumb">) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-3", className)}>
      <div className="min-w-0 space-y-0.5">
        <h2 className="text-section font-semibold text-foreground">{title}</h2>
        {description ? (
          <p className="text-meta text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 gap-2">{actions}</div> : null}
    </div>
  );
}
