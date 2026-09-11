"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Button, ButtonLink } from "@/components/ui";

/**
 * Something failed while rendering a page -- most often the API being
 * unreachable. Says "unavailable", not "not found": the listing may well exist.
 * Inside the locale layout, so the header, footer and translations still work.
 */
export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const t = useTranslations("errors");

  useEffect(() => {
    // The browser console only. The server already logged it with a request
    // id; the digest below is what ties a visitor's report to that line.
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-20 sm:py-28">
      <p className="text-sm font-semibold text-muted">{t("badge")}</p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
        {t("title")}
      </h1>
      <p className="mt-4 text-base text-muted">{t("body")}</p>
      {error.digest && (
        <p className="mt-2 text-xs text-muted">
          {t("reference", { digest: error.digest })}
        </p>
      )}
      <div className="mt-8 flex flex-wrap gap-3">
        <Button type="button" onClick={() => retry()}>
          {t("retry")}
        </Button>
        <ButtonLink href="/" variant="secondary">
          {t("home")}
        </ButtonLink>
      </div>
    </div>
  );
}
