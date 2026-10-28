"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Say what will actually happen, including any downstream effect. */
  description: React.ReactNode;
  /** Names the action ("Remove issuer"), never just "OK". */
  confirmLabel: string;
  onConfirm: () => void | Promise<void>;
  destructive?: boolean;
}

/** Confirmation for irreversible actions.
 *
 * Replaces `window.confirm`, which cannot be styled, ignores the design system, offers
 * no busy state, and reads as a browser malfunction rather than part of the product. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  destructive = true,
}: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      // Always clears, so a failed action leaves the dialog usable rather than stuck
      // behind a permanently disabled button.
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose
            render={
              <Button variant="ghost" size="sm" disabled={busy}>
                Cancel
              </Button>
            }
          />
          <Button
            size="sm"
            variant={destructive ? "destructive" : "default"}
            onClick={handleConfirm}
            pending={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
