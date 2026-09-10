import { getTranslations } from "next-intl/server";

import { ButtonLink } from "@/components/ui";

export async function CtaBand() {
  const t = await getTranslations("cta");

  return (
    <section className="border-y border-border-token bg-brand px-5 py-14 sm:py-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-brand-contrast sm:text-3xl">
            {t("title")}
          </h2>
          <p className="mt-2 max-w-xl text-sm text-brand-contrast/80">
            {t("subtitle")}
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-3 sm:flex-row">
          {/* `/signup`, not `/signup/seeker`. "Get started free" is the last
              thing on the homepage and names no audience, so sending it to the
              job-seeker form answered a question it had not asked. */}
          <ButtonLink
            href="/signup"
            variant="secondary"
            size="lg"
            className="border-transparent"
          >
            {t("primary")}
          </ButtonLink>
          <ButtonLink
            href="/contact"
            variant="ghost"
            size="lg"
            className="border border-brand-contrast/30 text-brand-contrast hover:bg-brand-strong hover:text-brand-contrast"
          >
            {t("secondary")}
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
