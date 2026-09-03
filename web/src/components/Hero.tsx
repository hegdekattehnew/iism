import { getTranslations } from "next-intl/server";

import { ButtonLink, buttonClass } from "@/components/ui";

export async function Hero() {
  const t = await getTranslations("hero");

  return (
    <section className="relative overflow-hidden border-b border-border-token bg-accent-soft">
      <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:py-24">
        <div className="max-w-3xl">
          <p className="inline-flex items-center rounded-full border border-border-token bg-surface px-3 py-1 text-xs font-semibold tracking-wide text-brand uppercase">
            {t("eyebrow")}
          </p>

          <h1 className="mt-5 text-3xl leading-tight font-bold tracking-tight sm:text-5xl sm:leading-[1.1]">
            {t("title")}
          </h1>

          <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
            {t("subtitle")}
          </p>

          {/* Primary entry action. Wired to the skills route for now; becomes the
              real search once Sprint 2 lands the taxonomy. */}
          <form
            action="/skills"
            className="mt-8 flex w-full max-w-2xl flex-col gap-2 sm:flex-row"
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
            <button type="submit" className={buttonClass("primary", "lg")}>
              {t("searchButton")}
            </button>
          </form>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href="/signin" size="lg">
              {t("primaryCta")}
            </ButtonLink>
            <ButtonLink href="/courses" variant="secondary" size="lg">
              {t("secondaryCta")}
            </ButtonLink>
          </div>

          <p className="mt-6 text-xs text-muted">{t("trust")}</p>
        </div>
      </div>
    </section>
  );
}
