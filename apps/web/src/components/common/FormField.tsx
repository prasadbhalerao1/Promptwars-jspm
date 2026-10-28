"use client";

import { useId } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  label: string;
  /** Receives the wiring the field needs; spread it onto the control. */
  children: (props: {
    id: string;
    "aria-describedby": string | undefined;
    "aria-invalid": boolean | undefined;
  }) => React.ReactNode;
  /** Guidance shown before the user makes a mistake, not after. */
  hint?: string;
  error?: string | null;
  required?: boolean;
  className?: string;
}

/** Label + control + hint/error, wired for assistive tech.
 *
 * Around 32 controls across the app were raw `<input className="border rounded-md …">`
 * with a detached `<label>` and no error wiring. This makes the accessible version the
 * path of least resistance: callers get `id`, `aria-describedby` and `aria-invalid`
 * without having to remember any of them. */
export function FormField({
  label,
  children,
  hint,
  error,
  required,
  className,
}: FormFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  // Errors supersede hints as the description, so a screen reader announces the problem
  // rather than the original guidance.
  const describedBy = error ? errorId : hint ? hintId : undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id} className="text-meta font-medium">
        {label}
        {required ? (
          <span aria-hidden className="ml-0.5 text-muted-foreground">
            *
          </span>
        ) : null}
        {!required ? (
          <span className="ml-1.5 font-normal text-muted-foreground">
            Optional
          </span>
        ) : null}
      </Label>

      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
      })}

      {error ? (
        <p id={errorId} role="alert" className="text-meta text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-meta text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
