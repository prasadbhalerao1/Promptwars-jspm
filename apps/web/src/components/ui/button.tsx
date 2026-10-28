import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/80",
        outline:
          "border-border bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

/** `pending` marks a button whose label swaps while an async action runs
 * ("Save changes" → "Saving…"). Screen readers otherwise announce nothing when
 * that text changes, so the button carries its own polite live region: the
 * label is the status. `aria-busy` additionally exposes the in-flight state to
 * assistive tech that reports it, and `disabled` prevents double-submits.
 *
 * Wired here rather than at each call site so all of them behave identically. */
function Button({
  className,
  variant = "default",
  size = "default",
  pending,
  disabled,
  nativeButton,
  render,
  ...props
}: ButtonPrimitive.Props &
  VariantProps<typeof buttonVariants> & { pending?: boolean }) {
  /** Base UI defaults `nativeButton` to `true`, which asserts the rendered element
   * really is a `<button>`. Every `render={<Link …/>}` call site renders an `<a>`
   * instead, so that default was wrong and Base UI logged an accessibility warning on
   * each one ("Rendering a non-<button> removes native button semantics"). More than a
   * console nuisance: with the flag wrong, Base UI skips the keyboard and role handling
   * that makes a non-button behave like one.
   *
   * Inferred from `render` rather than fixed at the call sites so links get correct
   * semantics automatically; an explicit `nativeButton` still wins for the rare case
   * that renders some other genuine button element. */
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      aria-live={pending === undefined ? undefined : "polite"}
      aria-busy={pending || undefined}
      disabled={disabled || pending}
      nativeButton={nativeButton ?? render === undefined}
      render={render}
      {...props}
    />
  );
}

export { Button, buttonVariants };
