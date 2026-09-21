"use client";

import type { ComponentProps, ReactNode } from "react";

const BASE =
  "mt-1.5 w-full rounded-lg border border-input-border bg-background px-3 py-2.5 text-sm " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function Text(props: ComponentProps<"input">) {
  return <input {...props} className={`${BASE} ${props.className ?? ""}`} />;
}

export function Area(props: ComponentProps<"textarea">) {
  return <textarea rows={3} {...props} className={`${BASE} ${props.className ?? ""}`} />;
}

export function Select(props: ComponentProps<"select">) {
  return <select {...props} className={`${BASE} ${props.className ?? ""}`} />;
}

export function Check({ label, ...props }: ComponentProps<"input"> & { label: string }) {
  return (
    <label className="flex items-center gap-2 py-2 text-sm">
      <input
        type="checkbox"
        {...props}
        className="h-4 w-4 rounded border-input-border accent-brand"
      />
      {label}
    </label>
  );
}

/** A saved row in a repeating section, with its edit and remove controls. */
export function EntryRow({
  title,
  subtitle,
  meta,
  onEdit,
  onRemove,
  editLabel,
  removeLabel,
}: {
  title: string;
  subtitle?: string | null;
  meta?: string | null;
  onEdit: () => void;
  onRemove: () => void;
  editLabel: string;
  removeLabel: string;
}) {
  return (
    <li className="flex flex-wrap items-start gap-3 rounded-lg border border-border-token bg-background px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title}</p>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        {meta && <p className="mt-0.5 text-xs text-muted">{meta}</p>}
      </div>
      <div className="flex shrink-0 gap-3 text-xs">
        <button type="button" onClick={onEdit} className="text-brand hover:underline">
          {editLabel}
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="text-muted hover:text-rose-600 hover:underline"
        >
          {removeLabel}
        </button>
      </div>
    </li>
  );
}
