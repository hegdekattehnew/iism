import { getTranslations, setRequestLocale } from "next-intl/server";

import { SearchResults } from "@/components/SearchResults";
import { buttonVariants } from "@/components/ui/button-variants";
import { getPathname } from "@/i18n/navigation";

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  // The homepage hero posts here as ?q=…
  const { q = "" } = await searchParams;
  const t = await getTranslations("searchPage");
  // Locale-prefixed, as the hero's own action is: a bare "/search" costs a
  // redirect on every refine.
  const action = getPathname({ href: "/search", locale });

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        {q.trim() ? t("title", { q: q.trim() }) : t("titleEmpty")}
      </h1>
      <form action={action} method="get" role="search" className="mt-6 flex gap-2">
        <label htmlFor="search-q" className="sr-only">
          {t("label")}
        </label>
        <input
          id="search-q"
          name="q"
          type="search"
          defaultValue={q}
          placeholder={t("placeholder")}
          className="w-full min-w-0 flex-1 rounded-lg border border-input-border bg-surface px-4 py-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        />
        <button type="submit" className={buttonVariants({ size: "lg", className: "shrink-0" })}>
          {t("submit")}
        </button>
      </form>
      <div className="mt-10">
        {/* Keyed by the query so a refined search starts clean. */}
        <SearchResults key={q} query={q} />
      </div>
    </div>
  );
}
