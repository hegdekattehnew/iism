import { getTranslations } from "next-intl/server";

import { ButtonLink } from "@/components/ui";

/** Every not-yet-built route renders this, so navigation is complete from day
 *  one and content can be dropped in without touching layout. */
export async function PlaceholderPage({
  titleKey,
  noteKey,
}: {
  titleKey: string;
  noteKey: string;
}) {
  const tn = await getTranslations("nav");
  const tf = await getTranslations("footer");
  const tp = await getTranslations("placeholder");

  const title = ["jobs", "courses", "skills", "forEmployers", "forProviders", "signIn"].includes(
    titleKey,
  )
    ? tn(titleKey)
    : tf(titleKey);

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-20 sm:py-28">
      <p className="inline-flex items-center rounded-full border border-border-token bg-surface-muted px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted">
        {tp("badge")}
      </p>
      <h1 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      <p className="mt-4 max-w-2xl text-base text-muted">{tp(noteKey)}</p>
      <p className="mt-2 max-w-2xl text-sm text-muted">{tp("body")}</p>
      <div className="mt-8">
        <ButtonLink href="/" variant="secondary" size="md">
          {tp("back")}
        </ButtonLink>
      </div>
    </div>
  );
}
