import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge class names, with later Tailwind utilities winning over earlier ones.
 *
 * `clsx` handles conditionals; `twMerge` resolves conflicts, so a caller passing
 * `className="px-6"` to a component whose base is `px-4` gets 6 rather than
 * both classes and whichever CSS order decides.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
