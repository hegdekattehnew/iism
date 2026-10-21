"use client";

/**
 * The form controls every editor in the product uses, under the names they have always had here.
 * Since Sprint 79 (BL-19.10) they are the library's own (`components/ui/field.tsx`): a label tied to
 * its control, a hint, a place for what is wrong, 44 px, and the checks that run when somebody leaves
 * a field. Writing `<Field label><Text minLength={3} /></Field>` is still all a form does, and the
 * limits stay literal where `constraints.test.ts` reads them.
 */
export {
  Checkbox as Check,
  Field,
  FormErrors,
  Input as Text,
  Select,
  Textarea as Area,
} from "@/components/ui/field";

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
      {/* `basis-48`, not `flex-1`: on a phone the two 44 px buttons would squeeze the title into a column
          four lines tall; this lets them drop below it instead. */}
      <div className="min-w-0 grow basis-48">
        <p className="text-sm font-medium">{title}</p>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        {meta && <p className="mt-0.5 text-xs text-muted">{meta}</p>}
      </div>
      {/* 44 px each (the row is the data's, the buttons are the page's), and named for their row: ten
          "Remove" buttons are ten identical names to a screen reader. The label contains the visible
          word, as a label must (WCAG 2.5.3). */}
      <div className="ml-auto flex max-w-full shrink-0 flex-wrap gap-1 text-sm">
        <button
          type="button"
          onClick={onEdit}
          aria-label={`${editLabel}: ${title}`}
          className="inline-flex min-h-11 items-center rounded-lg px-3 text-brand hover:underline"
        >
          {editLabel}
        </button>
        <button
          type="button"
          onClick={onRemove}
          aria-label={`${removeLabel}: ${title}`}
          className="inline-flex min-h-11 items-center rounded-lg px-3 text-muted hover:text-danger-text hover:underline"
        >
          {removeLabel}
        </button>
      </div>
    </li>
  );
}
