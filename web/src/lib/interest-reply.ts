/**
 * When a learner who registered interest may expect to hear back (Sprint 91, B22.2).
 *
 * Registering interest used to end in a status word and nothing else: no date, no next step. This
 * is the one number behind both halves of the answer, so the learner's "Reply expected by 14 Oct"
 * and the provider's "Waiting 4 days" cannot disagree about it.
 *
 * **It is an ask, not a guarantee.** A provider is a separate organisation and the platform cannot
 * make it answer, so the words are "expected" and "asked to", never "will". What the learner is
 * given is the date after which writing to us is reasonable (a contact link, no new endpoint).
 */
export const REPLY_WITHIN_DAYS = 3;

const DAY_MS = 24 * 60 * 60 * 1000;

/** The day after which a reply is overdue, from when the interest was registered. */
export function replyBy(registeredAt: string): Date {
  return new Date(new Date(registeredAt).getTime() + REPLY_WITHIN_DAYS * DAY_MS);
}

/** Whole days since the learner registered (never negative). */
export function daysWaiting(registeredAt: string, now: number): number {
  return Math.max(0, Math.floor((now - new Date(registeredAt).getTime()) / DAY_MS));
}

/** Overdue once the reply date has passed, so on the fourth day not the third. */
export function isReplyOverdue(registeredAt: string, now: number): boolean {
  return now > replyBy(registeredAt).getTime();
}
