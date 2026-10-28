"use client";

import { useState } from "react";
import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { WorkspaceNavList } from "@/components/common/WorkspaceNavList";
import {
  ROLE_LABELS,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

/** Workspace navigation on small screens.
 *
 * The sidebar previously just stacked above the content as a full-width block, so on a
 * phone a candidate met 12 links before reaching the page. A drawer keeps the same nav
 * one tap away without displacing content. */
export function MobileNav({ role }: { role: WorkspaceRole }) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            className="md:hidden"
            aria-label="Open navigation"
          >
            <Menu className="size-4" />
          </Button>
        }
      />
      <SheetContent side="left" className="w-72 p-0">
        <SheetHeader className="px-4 pt-4 pb-0">
          <SheetTitle className="text-meta font-medium text-muted-foreground">
            {ROLE_LABELS[role]}
          </SheetTitle>
        </SheetHeader>
        <div className="overflow-y-auto px-3 pb-6">
          {/* Closing on navigate: the drawer is fixed-position, so without this it
 would stay open over the page the user just asked for. */}
          <WorkspaceNavList role={role} onNavigate={() => setOpen(false)} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
