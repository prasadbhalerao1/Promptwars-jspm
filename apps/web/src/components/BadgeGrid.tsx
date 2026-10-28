import { Badge } from "@/components/ui/badge";
import type { BadgeResponse } from "@/lib/api";

export function BadgeGrid({ badges }: { badges: BadgeResponse[] }) {
  if (badges.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No badges yet - awarded when a skill is corroborated by 2+ independent
        sources (e.g. resume + GitHub language usage).
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {badges.map((badge) => (
        <Badge
          key={badge.id}
          variant="secondary"
          className="border border-primary bg-primary/10 text-primary hover:bg-primary/10 hover:border-primary transition-all font-semibold px-2.5 py-1 text-xs select-none capitalize"
          title={`Corroborated by: ${badge.corroboration_sources.join(", ")}`}
        >
          {badge.skill_name}
        </Badge>
      ))}
    </div>
  );
}
