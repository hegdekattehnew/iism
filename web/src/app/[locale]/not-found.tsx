import { getTranslations } from "next-intl/server";

import { ButtonLink } from "@/components/ui";
import { IconTile } from "@/components/ui/icon-tile";
import { SearchIcon } from "@/components/ui/icons";

/** Reached only by a genuine 404 -- see the detail pages, which used to call
 *  `notFound()` for any failure, so an API outage told visitors the listing
 *  did not exist. */
export default async function NotFound() {
  const t = await getTranslations("errors");
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-20 sm:py-28">
      <IconTile tone="neutral" className="mb-4">
        <SearchIcon />
      </IconTile>
      <p className="text-sm font-semibold text-muted">{t("notFoundBadge")}</p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
        {t("notFoundTitle")}
      </h1>
      <p className="mt-4 text-base text-muted">{t("notFoundBody")}</p>
      <div className="mt-8 flex flex-wrap gap-3">
        <ButtonLink href="/">{t("home")}</ButtonLink>
        <ButtonLink href="/jobs" variant="secondary">
          {t("browseJobs")}
        </ButtonLink>
      </div>
    </div>
  );
}
