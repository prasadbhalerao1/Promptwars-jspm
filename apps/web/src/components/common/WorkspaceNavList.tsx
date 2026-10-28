"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import {
  isNavItemActive,
  navSectionsFor,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

interface WorkspaceNavListProps {
  role: WorkspaceRole;
  /** Called after a nav link activates — used by the mobile drawer to close itself. */
  onNavigate?: () => void;
}

/** The nav link list, shared by the desktop sidebar and the mobile drawer so the two
 * can never drift apart. */
export function WorkspaceNavList({ role, onNavigate }: WorkspaceNavListProps) {
  const pathname = usePathname();
  const sections = navSectionsFor(role);

  return (
    <nav className="flex flex-col gap-5" aria-label="Workspace">
      {sections.map((section, sectionIndex) => (
        <div
          key={section.label ?? `section-${sectionIndex}`}
          className="flex flex-col gap-1"
        >
          {section.label ? (
            <h3 className="px-2 pb-1 text-meta font-medium text-muted-foreground">
              {section.label}
            </h3>
          ) : null}
          {section.items.map((item) => {
            const active = isNavItemActive(item, pathname);
            const Icon = item.icon;
            return (
              <Link
                key={`${item.href}-${item.label}`}
                href={item.href}
                onClick={onNavigate}
                // aria-current is what conveys "you are here" to assistive tech; the
                // background alone would be colour-only signalling.
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex items-center gap-2.5 rounded-md px-2 py-2 text-body outline-none transition-colors duration-(--animate-duration-fast)",
                  "focus-visible:ring-3 focus-visible:ring-ring/50",
                  active
                    ? "bg-sidebar-accent font-medium text-foreground before:absolute before:top-1.5 before:bottom-1.5 before:-left-1 before:w-0.5 before:rounded-full before:bg-primary before:content-['']"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                )}
              >
                <Icon
                  aria-hidden
                  className={cn("size-4 shrink-0", active && "text-primary")}
                />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
