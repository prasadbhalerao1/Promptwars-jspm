import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "progress" | "positive" | "attention" | "negative";

/** Status vocabulary, mapped to tone once so the same word never renders two ways in
 * two places. Keys are the literal strings the API returns.
 *
 * Tone is intentionally coarse — five tones, not one colour per status. A palette with
 * a distinct hue per value stops reading as status and starts reading as decoration. */
const STATUS_TONES: Record<string, Tone> = {
  // Application pipeline
  sourced: "neutral",
  screened: "progress",
  interview_scheduled: "progress",
  offered: "positive",
  hired: "positive",
  rejected: "negative",
  // Jobs / events
  draft: "neutral",
  active: "progress",
  open: "progress",
  closed: "neutral",
  completed: "positive",
  // Async work
  pending: "attention",
  processing: "progress",
  failed: "negative",
  // Fraud review
  upheld: "negative",
  dismissed: "neutral",
  approved: "positive",
};

const TONE_CLASS: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  progress: "text-info",
  positive: "text-success",
  attention: "text-warning",
  negative: "text-destructive",
};

/** Humanizes `interview_scheduled` → `Interview scheduled`. */
function humanize(status: string): string {
  const spaced = status.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: string;
  /** Overrides the humanized status text. */
  label?: string;
  className?: string;
}) {
  const tone = STATUS_TONES[status] ?? "neutral";

  return (
    // `outline` keeps the chip quiet: colour carries the tone, and the label carries
    // the meaning, so status is never communicated by colour alone.
    <Badge
      variant="outline"
      className={cn("font-normal", TONE_CLASS[tone], className)}
    >
      {label ?? humanize(status)}
    </Badge>
  );
}
