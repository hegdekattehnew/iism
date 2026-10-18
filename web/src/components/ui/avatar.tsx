import { cn } from "@/lib/cn";

/**
 * A mark for an organisation: its first letter on a tinted square (Sprint 84, BL-19.15).
 *
 * A logo would be better and the content security policy refuses remote images, so every employer and
 * training provider gets the same kind of mark and the **tint is picked from the name**, so the same
 * organisation is the same colour on every list and page. The four tints are semantic tones, so both
 * themes are covered by the tokens and nothing here names a colour. The tint carries no meaning (a
 * green mark is not a verified one): the verified mark is its own icon and words.
 *
 * Decorative: the name is always written beside it, so it is hidden from assistive technology.
 */
const TONES = [
  "bg-accent-soft text-brand",
  "bg-info-surface text-info-text",
  "bg-success-surface text-success-text",
  "bg-warning-surface text-warning-text",
] as const;

/**
 * A small stable number from a string (the same name always gives the same tone). Capitals are not
 * folded: with four tones the case of a letter (32 apart) never changes the result, so folding was a
 * claim a mutation check showed nothing could test.
 */
export function toneIndex(name: string): number {
  let h = 0;
  for (const ch of name.trim()) h = (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0;
  return h % TONES.length;
}

/** The first character that is a letter or a digit, upper-cased where the script has case; `?` if none. */
export function initialOf(name: string): string {
  for (const ch of Array.from(name.trim())) {
    if (/[\p{L}\p{N}]/u.test(ch)) return ch.toLocaleUpperCase();
  }
  return "?";
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-base font-semibold",
        TONES[toneIndex(name)],
        className,
      )}
    >
      {initialOf(name)}
    </span>
  );
}
