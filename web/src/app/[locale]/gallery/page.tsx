import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { Field, Input, Select, Checkbox } from "@/components/ui/field";
import { Alert, Badge, Button, Card, CardBody, Section } from "@/components/ui";
import { EmptyState } from "@/components/ui/empty-state";
import { BriefcaseIcon } from "@/components/ui/icons";
import { Spinner } from "@/components/ui/spinner";

/**
 * Every variant of the shared components on one page, for review (Sprint 80, BL-19.11, ADR-089).
 *
 * Switch the theme (the footer's Appearance) and the language to see each one in both. **It exists in
 * development and in the browser-test build, never in a production build** (`NEXT_PUBLIC_UI_GALLERY`,
 * set by `npm run build:e2e`): like `/status` it is a tool for whoever runs the stack, not a page.
 * The browser sweep visits it in both languages, in light and dark, so a variant whose colours stop
 * being readable in either theme fails there, which is most of what a gallery is for.
 */
const GALLERY_ENABLED =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_UI_GALLERY === "1";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  if (!GALLERY_ENABLED) notFound();
  const t = await getTranslations("gallery");

  return (
    <Section>
      <h1 className="text-3xl font-semibold">{t("title")}</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">{t("intro")}</p>

      <h2 className="mt-10 text-xl font-semibold">{t("surfaces")}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardBody>{t("levelDefault")}</CardBody>
        </Card>
        <Card level="raised">
          <CardBody>{t("levelRaised")}</CardBody>
        </Card>
        <Card>
          <CardBody>
            {t("levelDefault")}
            <Card level="inset" className="mt-3 p-3 text-sm">
              {t("levelInset")}
            </Card>
          </CardBody>
        </Card>
        <Card level="interactive">
          <CardBody>{t("levelInteractive")}</CardBody>
        </Card>
      </div>

      <h2 className="mt-10 text-xl font-semibold">{t("badges")}</h2>
      <div className="mt-4 space-y-3">
        {(["sm", "md"] as const).map((size) => (
          <div key={size} className="flex flex-wrap gap-2">
            <Badge size={size}>{t("badgeNeutral")}</Badge>
            <Badge size={size} tone="brand">{t("badgeBrand")}</Badge>
            <Badge size={size} tone="good">{t("badgeGood")}</Badge>
            <Badge size={size} tone="warn">{t("badgeWarn")}</Badge>
            <Badge size={size} tone="bad">{t("badgeBad")}</Badge>
            <Badge size={size} tone="info">{t("badgeInfo")}</Badge>
          </div>
        ))}
      </div>

      <h2 className="mt-10 text-xl font-semibold">{t("buttons")}</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button>{t("buttonPrimary")}</Button>
        <Button variant="secondary">{t("buttonSecondary")}</Button>
        <Button variant="soft">{t("buttonSoft")}</Button>
        <Button variant="ghost">{t("buttonGhost")}</Button>
        <Button variant="danger">{t("buttonDanger")}</Button>
        <Button loading>{t("buttonLoading")}</Button>
        <Button disabled>{t("buttonDisabled")}</Button>
      </div>

      <h2 className="mt-10 text-xl font-semibold">{t("alerts")}</h2>
      <div className="mt-4 max-w-xl space-y-3">
        <Alert tone="danger">{t("alertDanger")}</Alert>
        <Alert tone="warning">{t("alertWarning")}</Alert>
        <Alert tone="success" role="status">{t("alertSuccess")}</Alert>
        <Alert tone="info" role="status">{t("alertInfo")}</Alert>
      </div>

      <h2 className="mt-10 text-xl font-semibold">{t("empty")}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <EmptyState
          icon={BriefcaseIcon}
          title={t("emptyTitle")}
          action={<Button size="sm">{t("emptyAction")}</Button>}
        >
          {t("emptyBody")}
        </EmptyState>
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm text-muted">
            <Spinner label={t("spinner")} />
            {t("spinner")}
          </div>
          <p className="text-xs text-muted">{t("loadingPlaceholder")}</p>
          {/* The skeleton's own shape, without its `data-loading`, which would hide the footer here. */}
          <div className="h-36 w-full animate-pulse rounded-xl bg-surface-muted" />
        </div>
      </div>

      <h2 className="mt-10 text-xl font-semibold">{t("fields")}</h2>
      <div className="mt-4 grid max-w-3xl gap-4 sm:grid-cols-2">
        <Field label={t("fieldLabel")} hint={t("fieldHint")}>
          <Input defaultValue="Ward attendant" />
        </Field>
        <Field label={t("fieldLabel")} error={t("fieldError")}>
          <Input defaultValue="ab" />
        </Field>
        <Field label={t("fieldSelect")}>
          <Select defaultValue="gig">
            <option value="full_time">{t("optionOne")}</option>
            <option value="gig">{t("optionTwo")}</option>
          </Select>
        </Field>
        <Checkbox label={t("fieldCheck")} defaultChecked />
      </div>
    </Section>
  );
}
