import { Badge } from "@/components/ui/badge";
import type { AIContentSignal } from "@/lib/api";

/** FR-6 hard requirement: always shows a confidence label + rationale, never a bare
 * "AI-generated: yes/no" verdict (doc 04 §9). */
export function AIContentSignalBadge({
  signal,
}: {
  signal: AIContentSignal | null;
}) {
  if (!signal || signal.score === null) {
    return (
      <div className="space-y-1">
        <Badge variant="outline">
          AI-content signal: not enough text to assess
        </Badge>
      </div>
    );
  }

  const variant =
    signal.score >= 70
      ? "destructive"
      : signal.score >= 40
        ? "secondary"
        : "outline";

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={variant}>
          AI-likelihood signal: {signal.score.toFixed(0)}/100
        </Badge>
        <Badge variant="outline">confidence: {signal.confidence_label}</Badge>
        {signal.flagged_sections.length > 0 && (
          <Badge variant="outline">
            flagged: {signal.flagged_sections.join(", ")}
          </Badge>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{signal.rationale}</p>
    </div>
  );
}
