import { useState } from "react";

/**
 * A search box that starts from a term handed to the screen (the search screen's "see all", which
 * navigates here with `?q=`) and then belongs to the person typing.
 *
 * Syncing a prop into state with an effect is the pattern React 19's own lint rule forbids (it
 * renders once with the old term, then again); this adjusts the state while rendering, which is
 * the documented way: when the handed term changes, what was typed is dropped and the new one shows.
 */
export function useSeededTerm(handed: string | undefined): [string, (next: string) => void] {
  const [typed, setTyped] = useState<string | null>(null);
  const [seen, setSeen] = useState(handed);
  if (handed !== seen) {
    setSeen(handed);
    setTyped(null);
  }
  return [typed ?? handed ?? "", setTyped];
}
