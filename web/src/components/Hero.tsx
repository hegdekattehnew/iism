import { getLocale, getTranslations } from "next-intl/server";

import { RoleChooser } from "@/components/RoleChooser";
import { buttonVariants } from "@/components/ui";
import { Link, getPathname } from "@/i18n/navigation";

export async function Hero() {
  const t = await getTranslations("hero");
  const locale = await getLocale();

  // Locale-aware. `routing.ts` sets no `localePrefix`, so the default "always"
  // applies and a bare `action="/skills"` costs a 307 to `/{locale}/skills` --
  // a wasted round trip on mobile data, on the hero's primary action.
  const searchAction = getPathname({ href: "/skills", locale });

  return (
    <section className="relative overflow-hidden border-b border-border-token bg-accent-soft">
      <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:py-20 lg:py-24">
        {/* Two columns only from `lg`: at `md` the copy track would be ~420px
            with `sm:text-4xl` already in force.

            `minmax(0,1fr)`, never `1fr`. A `1fr` track has `min-width:auto`, so
            the search row -- a `w-full flex-1` input beside an unshrinkable
            `size="lg"` submit -- can force this track past the container and
            push the chooser off the right edge. The section carries
            `overflow-hidden`, so that produces no scrollbar and no error: the
            card would simply vanish. */}
        <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-12">
          {/* The copy column is first in the DOM, so on a phone the search box
              stays the first thing a thumb reaches and the chooser stacks after
              it. No `order-*`: reading order and visual order must not diverge. */}
          <div className="min-w-0">
            <p className="inline-flex items-center rounded-full border border-border-token bg-surface px-3 py-1 text-xs font-semibold tracking-wide text-brand uppercase">
              {t("eyebrow")}
            </p>

            {/* `sm:text-5xl` became `sm:text-4xl lg:text-5xl`: this column is
                narrower than the `max-w-3xl` it used to have, and the old 48px
                step set four ragged lines in it. */}
            <h1 className="mt-5 text-3xl leading-tight font-bold tracking-tight sm:text-4xl lg:text-5xl lg:leading-[1.1]">
              {t("title")}
            </h1>

            <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
              {t("subtitle")}
            </p>

            {/* The one primary action, and the only one that gives a visitor
                something without an account. Everything above it is on a fold
                budget: at 375x667 this button's bottom sits around 540px, and
                `html[lang="hi"]` carries line-height 1.7, which is the binding
                case. Do not add height above this. */}
            <form
              action={searchAction}
              className="mt-6 flex w-full max-w-2xl flex-col gap-2 sm:flex-row"
            >
              <label htmlFor="hero-search" className="sr-only">
                {t("searchLabel")}
              </label>
              <input
                id="hero-search"
                name="q"
                type="search"
                placeholder={t("searchPlaceholder")}
                className="w-full flex-1 rounded-lg border border-border-token bg-surface px-4 py-3 text-base text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              />
              <button
                type="submit"
                className={buttonVariants({ variant: "primary", size: "lg" })}
              >
                {t("searchButton")}
              </button>
            </form>

            {/* Was a `size="lg"` secondary button. Kept, because it is the
                hero's only no-signup escape hatch and `BrowsePanels` is four
                sections down -- but demoted, because a large secondary button
                beside a large primary submit makes neither read as primary.
                The old "Get my recommendations" button is gone entirely: it
                pointed at `/signup/seeker`, which is now the chooser's first
                row, and the same href twice in one viewport is not a choice. */}
            <p className="mt-4 text-sm">
              <Link
                href="/courses"
                className="font-medium text-brand underline-offset-4 hover:text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                {t("browseLink")}
              </Link>
            </p>

            <p className="mt-6 text-xs text-muted">{t("trust")}</p>
          </div>

          {/* `max-w-md` while stacked, or at tablet this is a 728px-wide card
              holding three short labels. */}
          <RoleChooser className="w-full max-w-md lg:max-w-none" />
        </div>
      </div>
    </section>
  );
}
