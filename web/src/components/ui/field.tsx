"use client";

import {
  createContext,
  useContext,
  useId,
  useState,
  isValidElement,
  type ChangeEvent,
  type ChangeEventHandler,
  type ComponentProps,
  type FocusEvent,
  type FocusEventHandler,
  type ReactNode,
} from "react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";

/**
 * Form controls with a label, a hint and a place for what is wrong (Sprint 79, BL-19.10, ADR-088).
 *
 * `Field` wraps one control (`Input`, `Textarea` or `Select`) and wires it: the label is attached by
 * `htmlFor`, the hint and the problem are named by `aria-describedby`, and `aria-invalid` is set while
 * there is a problem. The control reads all of that from context, so a call site writes
 * `<Field label hint><Input minLength={3} /></Field>` and nothing else: the limits stay literal
 * at the control, where `constraints.test.ts` reads them.
 *
 * **A problem is shown next to its field**, from three places and in this order: the `error` a form
 * passes, **what the server said about this field** (`FormErrors`, keyed by the schema's field name),
 * and what the browser's own constraints say **when the person leaves the field**, in the page's
 * language (`form.*` messages: the browser's wording follows the browser's language, not the page's).
 * A server message goes away when the person edits that field, and a local one once it is fixed.
 * Submitting still uses the browser's validation, so nothing here can let a bad value through. The
 * checks themselves (`validate.ts`) load the first time a field is left, to keep forms off the first
 * load of every route that has one.
 */

type FieldState = {
  id: string;
  describedBy: string | undefined;
  invalid: boolean;
  /** Called by the control when it loses focus, and after a change while a problem is showing. */
  check: (element: ValidatableControl, event: "blur" | "change") => void;
};

type ValidatableControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const FieldContext = createContext<FieldState | null>(null);
const ServerErrors = createContext<Readonly<Record<string, string>>>({});

/** Gives every `Field` below it the server's per-field messages from a failed save. */
export function FormErrors({
  fields,
  children,
}: {
  fields: Readonly<Record<string, string>> | undefined;
  children: ReactNode;
}) {
  return <ServerErrors.Provider value={fields ?? NONE}>{children}</ServerErrors.Provider>;
}
const NONE: Readonly<Record<string, string>> = {};

export function Field({
  label,
  hint,
  error,
  name,
  className,
  children,
}: {
  label: string;
  hint?: string;
  /** A problem the form already knows about; shown before anything else. */
  error?: string;
  /** The schema's name for the field, so the server's message about it lands here (else the control's `name`). */
  name?: string;
  className?: string;
  children: ReactNode;
}) {
  const t = useTranslations("form");
  const id = useId();
  // The control's own `name` is the schema's field name in every form here (they read their values
  // from `FormData`), so a form need not say it twice.
  const controlName = isValidElement(children) ? (children.props as { name?: string }).name : undefined;
  const server = useContext(ServerErrors)[name ?? controlName ?? ""];
  const [local, setLocal] = useState<string | null>(null);
  // The server's message about a field the person has since edited is stale: remember which one was
  // dismissed, so a new refusal (a different message) shows again.
  const [dismissed, setDismissed] = useState<string | null>(null);

  const problem = error ?? (server && server !== dismissed ? server : null) ?? local;
  const describedBy = [hint ? `${id}-hint` : null, problem ? `${id}-error` : null].filter(Boolean).join(" ");

  const state: FieldState = {
    id,
    describedBy: describedBy || undefined,
    invalid: Boolean(problem),
    check: (element, event) => {
      if (event === "change") {
        if (server) setDismissed(server);
        if (local === null) return; // a field that has not complained is not nagged mid-typing
      }
      void import("./validate").then(({ problemWith }) => {
        const found = problemWith(element);
        setLocal(found ? t(found.key, found.values) : null);
      });
    },
  };

  return (
    <div className={className}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <FieldContext.Provider value={state}>{children}</FieldContext.Provider>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-muted">
          {hint}
        </p>
      )}
      {problem && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm font-medium text-danger-text">
          {problem}
        </p>
      )}
    </div>
  );
}

const CONTROL =
  "mt-1.5 block min-h-11 w-full rounded-lg border bg-background px-3 py-2.5 text-sm " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

type Wirable<E extends ValidatableControl> = {
  id?: string;
  className?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean | "true" | "false" | "grammar" | "spelling";
  onBlur?: FocusEventHandler<E>;
  onChange?: ChangeEventHandler<E>;
};

/**
 * What every control takes from its `Field`: the id the label points at, what describes it, whether it
 * is invalid, and the two events that ask the field to check it. A control outside a `Field` gets only
 * the look and the 44 px height.
 */
function useWired<E extends ValidatableControl>(props: Wirable<E>) {
  const field = useContext(FieldContext);
  return {
    id: field?.id ?? props.id,
    "aria-describedby": field?.describedBy ?? props["aria-describedby"],
    "aria-invalid": field?.invalid ? true : props["aria-invalid"],
    className: cn(CONTROL, field?.invalid ? "border-danger-solid" : "border-input-border", props.className),
    onBlur: (e: FocusEvent<E>) => {
      props.onBlur?.(e);
      field?.check(e.currentTarget, "blur");
    },
    onChange: (e: ChangeEvent<E>) => {
      props.onChange?.(e);
      field?.check(e.currentTarget, "change");
    },
  };
}

export function Input(props: ComponentProps<"input">) {
  return <input {...props} {...useWired<HTMLInputElement>(props)} />;
}

export function Textarea(props: ComponentProps<"textarea">) {
  return <textarea rows={3} {...props} {...useWired<HTMLTextAreaElement>(props)} />;
}

export function Select(props: ComponentProps<"select">) {
  return <select {...props} {...useWired<HTMLSelectElement>(props)} />;
}

/**
 * A checkbox with its own label. The whole label is the target (44 px tall), not the 20 px box, which
 * is what a thumb lands on and what WCAG 2.5.8 measures.
 */
export function Checkbox({ label, className, ...props }: ComponentProps<"input"> & { label: string }) {
  return (
    <label className={cn("flex min-h-11 items-center gap-2 py-2 text-sm", className)}>
      <input type="checkbox" {...props} className="h-5 w-5 shrink-0 rounded-md border-input-border accent-brand" />
      {label}
    </label>
  );
}
