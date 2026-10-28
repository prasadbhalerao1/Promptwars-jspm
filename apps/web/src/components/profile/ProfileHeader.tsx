interface ProfileHeaderProps {
  username: string;
  headline: string | null;
  location: string | null;
  overallScore: number | null;
}

/** Public-profile header — read-only equivalent of ProfileSidebar's identity block,
 * used on the unauthenticated SSR `/[username]` page (no toggle/refresh controls there). */
export function ProfileHeader({
  username,
  headline,
  location,
  overallScore,
}: ProfileHeaderProps) {
  return (
    <header className="space-y-1">
      <h1 className="font-heading text-3xl font-semibold text-foreground">
        {username}
      </h1>
      {headline && <p className="text-lg text-muted-foreground">{headline}</p>}
      <p className="text-sm text-muted-foreground">
        {[
          location,
          overallScore !== null
            ? `Talent Score ${overallScore.toFixed(1)}`
            : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </header>
  );
}
