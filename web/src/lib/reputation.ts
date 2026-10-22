/**
 * When a rating is shown to the public (Sprint 92, B22.4).
 *
 * The vacancy page said "Rated by workers: 4 out of 5 from 1 rating": a score from one person, read
 * as a verdict on an organisation. A rating is shown from **three** ratings; below that the page
 * says there are not enough to show a score (and says nothing for none). The person's own
 * dashboard still shows its own ratings and count: it is theirs, not a public verdict.
 *
 * One number in one place, so the page and its test cannot disagree about it.
 */
export const MIN_RATINGS_TO_SHOW = 3;

export type PosterRating = { average: number; count: number };

/** `shown` when there are enough to say a score, `few` when there are some but not enough, `none` otherwise. */
export function ratingDisplay(rated: PosterRating | null): "shown" | "few" | "none" {
  if (!rated || rated.count <= 0) return "none";
  return rated.count >= MIN_RATINGS_TO_SHOW ? "shown" : "few";
}
