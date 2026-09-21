import { getTranslations } from "next-intl/server";
import { Fragment } from "react";

import { Link } from "@/i18n/navigation";
import { GRIEVANCE_OFFICER, PRIVACY_NOTICE_VERSION } from "@/lib/legal";

type Doc = "privacy" | "terms" | "grievance";
type Section = { title: string; body: string[] };

/**
 * The privacy notice, the terms and the grievance page.
 *
 * They replaced `PlaceholderPage` in Sprint 20, because signup now asks people
 * to agree to them and consent to a placeholder is not consent. Every page says
 * **draft pending legal review** until a lawyer has read it: the text describes
 * what the product actually does today, which is necessary but not sufficient.
 *
 * Sections live in the message files as arrays (read with `t.raw`) so the
 * Hindi text is a translation of the same structure, not a second document.
 */
export async function LegalPage({ doc }: { doc: Doc }) {
  const t = await getTranslations("legal");
  const sections = t.raw(`${doc}.sections`) as Section[];
  const officer = [
    ["officerName", GRIEVANCE_OFFICER.name],
    ["officerEmail", GRIEVANCE_OFFICER.email],
    ["officerPhone", GRIEVANCE_OFFICER.phone],
    ["officerAddress", GRIEVANCE_OFFICER.address],
  ] as const;

  return (
    <article className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <p className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
        {t("draftBadge")}
      </p>
      <h1 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
        {t(`${doc}.title`)}
      </h1>
      {doc !== "grievance" && (
        <p className="mt-2 text-sm text-muted">
          {t("version", { version: PRIVACY_NOTICE_VERSION })}
        </p>
      )}
      <p className="mt-6 text-base leading-relaxed">{t(`${doc}.intro`)}</p>
      <p className="mt-3 text-sm text-muted">{t("draftNote")}</p>

      {doc === "grievance" && (
        <section
          aria-labelledby="officer"
          className="mt-8 rounded-xl border border-border-token bg-surface p-5"
        >
          <h2 id="officer" className="text-lg font-semibold">
            {t("officerHeading")}
          </h2>
          <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
            {officer.map(([label, value]) => (
              <Fragment key={label}>
                <dt className="text-muted">{t(label)}</dt>
                <dd>{value ?? t("toBeAppointed")}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      )}

      {sections.map((section) => (
        <section key={section.title} className="mt-10">
          <h2 className="text-xl font-semibold">{section.title}</h2>
          {section.body.map((paragraph) => (
            <p key={paragraph} className="mt-3 text-base leading-relaxed">
              {paragraph}
            </p>
          ))}
        </section>
      ))}

      <p className="mt-12 text-sm">
        <Link
          href="/account"
          className="text-brand underline-offset-4 hover:underline"
        >
          {t("accountLink")}
        </Link>
      </p>
    </article>
  );
}
