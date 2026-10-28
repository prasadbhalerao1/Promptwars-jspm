"use client";

import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface FieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Shown once the user has tried to advance, so the form doesn't scold them for
   * fields they simply haven't reached yet. */
  error?: string | null;
  hint?: string;
  required?: boolean;
  autoFocus?: boolean;
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
  error,
  hint,
  required,
  autoFocus,
}: FieldProps) {
  // useId rather than a slugified label: two fields could share a label across steps,
  // and duplicate ids would make one label focus the wrong input.
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-medium text-foreground">
        {label}
        {!required && (
          <span className="ml-1.5 text-meta font-normal text-muted-foreground">
            optional
          </span>
        )}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        // The Input primitive already styles its own aria-invalid state, so the
        // error appearance follows from the ARIA attribute rather than a parallel
        // set of colour classes that could drift from it.
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
