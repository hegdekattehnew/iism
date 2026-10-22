"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";

/**
 * What a training organisation does: sells courses, delivers training, or both (Sprint 94, ADR-102).
 *
 * One organisation with two capabilities, never two accounts: a provider that only sells a course, one
 * that also delivers it, and one that only delivers courses other providers have authorised are all the
 * same kind of organisation with different boxes ticked. The control is on every surface that creates
 * a training organisation (sign-up, a signed-in person adding one, the header's "Create an
 * organisation") and in its settings, so the two words mean the same thing everywhere.
 *
 * Nothing here decides whether the choice is allowed: an organisation must do at least one, which the
 * form uses to hold its button and the server refuses again (422 at creation, 409 when changing).
 */
export type Capabilities = { sells: boolean; delivers: boolean };

/** What a provider was before capabilities existed, and what the form starts on. */
export const DEFAULT_CAPABILITIES: Capabilities = { sells: true, delivers: false };

export const doesSomething = (c: Capabilities) => c.sells || c.delivers;

const OPTIONS = [
  { key: "sells", name: "sells", hint: "sellsHint" },
  { key: "delivers", name: "delivers", hint: "deliversHint" },
] as const;

export function TrainingCapabilities({
  value,
  onChange,
  disabled = false,
  className,
}: {
  value: Capabilities;
  onChange: (next: Capabilities) => void;
  disabled?: boolean;
  className?: string;
}) {
  const t = useTranslations("capabilities");
  return (
    <fieldset className={cn("min-w-0", className)} disabled={disabled}>
      <legend className="text-sm font-medium">{t("legend")}</legend>
      <div className="mt-2 space-y-2">
        {OPTIONS.map(({ key, name, hint }) => (
          <label
            key={key}
            className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-border-token bg-surface px-3 py-2"
          >
            <input
              type="checkbox"
              checked={value[key]}
              onChange={(e) => onChange({ ...value, [key]: e.target.checked })}
              className="mt-0.5 h-5 w-5 shrink-0 rounded-md border-input-border accent-brand"
            />
            <span className="min-w-0">
              <span className="block text-sm font-medium">{t(name)}</span>
              <span className="mt-0.5 block text-xs text-muted">{t(hint)}</span>
            </span>
          </label>
        ))}
      </div>
      {!doesSomething(value) && (
        <p role="alert" className="mt-2 text-sm text-danger-text">
          {t("none")}
        </p>
      )}
    </fieldset>
  );
}
