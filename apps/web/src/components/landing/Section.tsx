import { cn } from "@/lib/utils";

/** Shell for the landing page's scenes.
 *
 * The page is one continuous narrative - signals become a profile, the profile becomes a
 * match, the match becomes a hire - so scenes are numbered like a sequence. But numbering
 * is the only thing they share: an earlier version of this shell forced every scene into
 * the same width, the same vertical rhythm and `overflow-hidden`, and the result read as
 * one template repeated nine times rather than nine different ideas.
 *
 * So the three things that made the page monotonous are all per-scene now:
 *
 * - **`width`** - a scene can run at reading width, workspace width, wide, or edge to
 *   edge. Product interfaces are supposed to break out of the text column.
 * - **`pad`** - vertical rhythm varies, because a full-viewport scene and an editorial
 *   statement should not breathe identically.
 * - **overflow is visible by default**, which is what allows an interface to overlap a
 *   neighbouring scene or bleed off the side. Pass `clip` only when a scene genuinely
 *   needs to crop something.
 */

/** Content widths.
 *
 * `workspace` (78rem) is the app's own container and is deliberately conservative for a
 * dense product UI. The landing page is art-directed for a laptop instead, so its
 * default runs wider - at 1440 the app width leaves ~100px of margin either side and
 * makes an expansive screen feel like a narrow one. */
const WIDTH = {
  reading: "mx-auto max-w-3xl",
  workspace: "mx-auto max-w-[88rem]",
  wide: "mx-auto max-w-[104rem]",
  full: "w-full",
} as const;

/** Vertical rhythm.
 *
 * These are deliberately smaller than they look like they should be, because padding
 * *stacks*: a `loose` scene followed by another `loose` scene put 176px of nothing on
 * top of 176px of nothing, and a measured pass found twelve dead bands averaging 340px -
 * close to 4,000px of empty page. Whitespace has to frame something; at that size it
 * simply reads as the page having run out of content.
 *
 * So the ceiling is lower, and scenes carry their own asymmetry (more room above a
 * scene mark than below its content) rather than relying on a symmetric block. */
const PAD = {
  none: "",
  tight: "py-14 lg:py-16",
  base: "py-16 lg:py-24",
  loose: "py-20 lg:py-28",
} as const;

export function Section({
  id,
  surface = "base",
  width = "workspace",
  pad = "base",
  clip = false,
  className,
  innerClassName,
  children,
}: {
  id?: string;
  surface?: "base" | "sunken";
  width?: keyof typeof WIDTH;
  pad?: keyof typeof PAD;
  /** Crop overflowing children. Off by default so interfaces can break the grid. */
  clip?: boolean;
  className?: string;
  innerClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={cn(
        "relative isolate",
        clip && "overflow-hidden",
        surface === "sunken" ? "bg-surface-sunken" : "bg-background",
        className,
      )}
    >
      <div className={cn("w-full px-6", PAD[pad], WIDTH[width], innerClassName)}>
        {children}
      </div>
    </section>
  );
}

/** The scene marker: an index paired with the name of what the scene does.
 *
 * Structural, not decorative. The previous version was a giant ghosted numeral floating
 * in a corner at 3.5% opacity, which consumed a large amount of visual real estate while
 * carrying no information - exactly the "decoration where a composition should be"
 * problem. Here the number is small, sharp, and sits in a rule that the scene's content
 * aligns against, so it reads as an instrument's index rather than as wallpaper.
 */
export function SceneMark({
  index,
  label,
  className,
}: {
  /** Two-digit index (`"01"`). */
  index: string;
  /** What this scene is: `SIGNALS`, `INTELLIGENCE`, `VERIFICATION`. */
  label: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span
        aria-hidden
        className="font-mono text-meta font-medium text-primary tabular-nums"
      >
        {index}
      </span>
      <span aria-hidden className="h-px w-8 bg-border" />
      <span className="font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </span>
    </div>
  );
}

/** Small system label: `SOURCE / GITHUB`, `CONFIDENCE / HIGH`, `EVIDENCE LAYER`.
 *
 * Quiet technical texture. Uppercase mono at meta size, never larger - at any bigger
 * size this stops reading as an instrument panel and starts reading as terminal cosplay,
 * which is the thing the brief explicitly rules out.
 */
export function SystemLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-mono text-meta font-medium tracking-[0.14em] text-muted-foreground uppercase",
        className,
      )}
    >
      {children}
    </p>
  );
}

/** A tiny label pinned against a large interface: `MATCH VECTOR / 0.94`.
 *
 * These are what make an oversized product surface read as engineered rather than as a
 * screenshot. Used sparingly - a dozen of them on one screen is noise, and they are
 * `aria-hidden` because they annotate a visual that already carries its own accessible
 * text.
 */
export function Annotation({
  label,
  value,
  className,
}: {
  label: string;
  value?: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "pointer-events-none inline-flex items-center gap-1.5 font-mono text-[0.6875rem] tracking-[0.12em] uppercase",
        className,
      )}
    >
      <span className="text-muted-foreground/70">{label}</span>
      {value ? <span className="text-foreground/70">{value}</span> : null}
    </span>
  );
}
