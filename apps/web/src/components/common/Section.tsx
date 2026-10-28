import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface SectionProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  children: React.ReactNode;
}

/** Standard "titled card" wrapper shared by every dashboard section, so each section
 * component owns only its content, not header/card boilerplate.
 *
 * The staggered fade-in this used to carry is gone: it delayed each section by
 * `index * 50ms`, so a dashboard of eight sections spent half a second assembling
 * itself on every visit. Motion should communicate a state change, and "the page
 * loaded" is not one. Dropping it also removes framer-motion from every dashboard
 * route's critical path. */
export function Section({
  title,
  subtitle,
  action,
  className,
  contentClassName,
  children,
}: SectionProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <CardTitle className="text-section font-semibold text-foreground">
            {title}
          </CardTitle>
          {subtitle ? (
            <p className="text-meta text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        {action}
      </CardHeader>
      <CardContent className={contentClassName}>{children}</CardContent>
    </Card>
  );
}
