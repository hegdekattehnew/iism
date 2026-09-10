import { getTranslations } from "next-intl/server";

import { Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";

/**
 * The three ways into an account, as one control.
 *
 * A newcomer had no way to learn the other two existed. The header's "Get
 * started" pointed at `/signup/seeker` and the only mention of employers or
 * training providers was two screens down the homepage, so an employer arriving
 * at the top of the page was offered a job-seeker signup and nothing else.
 *
 * **"I'm here to…", not "Which of these are you?"** ADR-038 is explicit that a
 * person is not an actor type -- the same human is a candidate looking for work
 * and the hiring manager at the clinic that employs them. A picker asking *who
 * you are* would contradict the identity model underneath it. Asking what you
 * want to do is both truer and asks for less commitment, and the footer note
 * carries the rest: it is one account, and a second role can be added later.
 *
 * **One card, not three.** `Audiences` further down the homepage is three peer
 * cards making three arguments; this is a single control presenting a single
 * decision, and the shapes have to differ or the page reads as repeating itself.
 *
 * Deliberately server-rendered with no state: three links do this with no
 * client bundle at all, and the target device is a low-end Android.
 */

const ROLES = [
  { key: "seeker", href: "/signup/seeker" },
  { key: "employer", href: "/signup/employer" },
  { key: "provider", href: "/signup/provider" },
] as const;

export async function RoleChooser({ className = "" }: { className?: string }) {
  const t = await getTranslations("chooser");

  return (
    // `overflow-hidden` so the first row's hover fill cannot square off the
    // card's rounded corner. That clip is why the rows below use an *inset*
    // focus ring: an outward one would be cropped on the first and last row.
    <Card className={`overflow-hidden ${className}`}>
      <h2
        id="role-chooser-title"
        className="border-b border-border-token px-5 py-4 text-sm font-semibold"
      >
        {t("title")}
      </h2>

      {/* `border-t` per row rather than `divide-y` on the list: `divide-y`
          compiles here (the colour resolves) but emits no border *width*, so
          the rows ran together with nothing between them. Computed
          `borderTopWidth` was `0px` on every row. */}
      <ul aria-labelledby="role-chooser-title">
        {ROLES.map(({ key, href }) => (
          <li
            key={key}
            className="border-t border-border-token first:border-t-0"
          >
            <Link
              href={href}
              className="flex items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-surface-muted focus-visible:-outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand"
            >
              <span className="min-w-0">
                <span className="block text-base font-semibold">
                  {t(`${key}Label`)}
                </span>
                {/* The credential, and it repeats for the two organisation
                    rows on purpose: it tells an employer the two org paths
                    behave identically, and warns them off the seeker row
                    before they meet a phone-OTP form. */}
                <span className="mt-0.5 block text-xs text-muted">
                  {t(`${key}Meta`)}
                </span>
              </span>
              <svg
                viewBox="0 0 24 24"
                aria-hidden
                className="h-4 w-4 shrink-0 text-muted"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m9 6 6 6-6 6" />
              </svg>
            </Link>
          </li>
        ))}
      </ul>

      <p className="border-t border-border-token bg-surface-muted px-5 py-3 text-xs text-muted">
        {t("note")}
      </p>
    </Card>
  );
}
