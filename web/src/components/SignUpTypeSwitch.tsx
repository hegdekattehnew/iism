import { useTranslations } from "next-intl";

import type { SignUpType } from "@/components/SignUpForm";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

const TYPES: SignUpType[] = ["seeker", "employer", "provider"];

/**
 * Which kind of account this registration is for -- changeable on the page.
 *
 * `/signup/[type]` used to render exactly one form, fixed by the URL. Arrive
 * at `/signup/seeker` from the chooser's first row, a bookmark or a typed
 * address, and the page offered phone registration and nothing else; an
 * employer or a training provider who landed there had to find the browser's
 * back button. Registration is for all three, so the page offers all three.
 *
 * Plain links, not a client-side toggle. The type is still carried by the URL,
 * so `/signup/employer` stays a shareable address that the audience pages can
 * link to; switching needs no JavaScript, which matters on the target device;
 * and `replace` keeps three taps from becoming three Back presses.
 *
 * "Find work", not "Job seeker": the same framing as `RoleChooser` -- what you
 * are here to do, not what kind of person you are (ADR-038).
 */
export function SignUpTypeSwitch({ current }: { current: SignUpType }) {
  const t = useTranslations("signup");
  const tc = useTranslations("chooser");

  return (
    <nav aria-label={tc("title")} className="mx-auto w-full max-w-md">
      <p className="mb-2 text-center text-xs font-semibold tracking-wide text-muted uppercase">
        {tc("title")}
      </p>
      <div className="grid grid-cols-3 gap-1 rounded-lg border border-border-token bg-surface p-1">
        {TYPES.map((type) => {
          const active = type === current;
          return (
            <Link
              key={type}
              href={`/signup/${type}`}
              replace
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-2 py-2 text-center text-sm leading-tight font-medium transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
                active
                  ? "bg-brand text-brand-contrast"
                  : "text-muted hover:bg-surface-muted hover:text-foreground",
              )}
            >
              {t(`switch.${type}`)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
