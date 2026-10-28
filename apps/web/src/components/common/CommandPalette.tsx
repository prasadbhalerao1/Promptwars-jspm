"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  navSectionsFor,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

/** ⌘K navigation across everything the current role can reach.
 *
 * Worth having here specifically because the candidate sidebar carries a dozen
 * destinations across four groups: typing two letters beats scanning a rail. Scoped to
 * the viewer's own nav so it can never offer a route their role would be bounced from.
 */
export function CommandPalette({ role }: { role: WorkspaceRole }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "k" || !(event.metaKey || event.ctrlKey)) return;
      // Otherwise the browser's own find/search bar opens over the palette.
      event.preventDefault();
      setOpen((previous) => !previous);
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const sections = navSectionsFor(role);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Navigate"
      description="Jump to any page in your workspace."
    >
      <CommandInput placeholder="Go to…" />
      <CommandList>
        <CommandEmpty>No matching page.</CommandEmpty>
        {sections.map((section, index) => (
          <CommandGroup
            key={section.label ?? `group-${index}`}
            heading={section.label ?? "Workspace"}
          >
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <CommandItem
                  key={`${item.href}-${item.label}`}
                  // cmdk matches on `value`, so without the label here typing the page
                  // name would filter everything out and match on the href instead.
                  value={item.label}
                  onSelect={() => go(item.href)}
                >
                  <Icon aria-hidden className="size-4 text-muted-foreground" />
                  {item.label}
                </CommandItem>
              );
            })}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
