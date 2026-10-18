/**
 * What is wrong with a form control's value (Sprint 79, BL-19.10, ADR-088).
 *
 * Its own module so a form pays for it **when a field is first left**, not on every route that has a
 * form: `Field` imports it dynamically, and `/profile` (the route closest to the first-load ceiling)
 * is made of forms.
 */

type ValidatableControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/** What is wrong with a control's value, as a message key and the numbers it names, or null. */
export function problemWith(
  element: ValidatableControl,
): { key: string; values?: { min?: number | string; max?: number | string } } | null {
  const v = element.validity;
  const text = element instanceof HTMLSelectElement ? null : element;
  // `validity.tooShort` is only ever true after a person has typed in the field, so a value that was
  // filled in by a script, or restored by the browser, would pass the native check and fail the server's.
  if (text && text.minLength > 0 && text.value.length > 0 && text.value.length < text.minLength) {
    return { key: "tooShort", values: { min: text.minLength } };
  }
  if (text && text.maxLength >= 0 && text.value.length > text.maxLength) {
    return { key: "tooLong", values: { max: text.maxLength } };
  }
  if (v.valueMissing) return { key: "required" };
  if (v.typeMismatch) return { key: (element as HTMLInputElement).type === "url" ? "typeUrl" : "typeEmail" };
  if (v.badInput) return { key: "badInput" };
  if (v.rangeUnderflow) return { key: "rangeUnderflow", values: { min: (element as HTMLInputElement).min } };
  if (v.rangeOverflow) return { key: "rangeOverflow", values: { max: (element as HTMLInputElement).max } };
  if (v.patternMismatch) return { key: "pattern" };
  return null;
}

