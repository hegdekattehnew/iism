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
          className="text-muted hover:text-danger-text hover:underline"
        >
          {removeLabel}
        </button>
      </div>
    </li>
  );
}
