"use client";

import { useTranslations } from "next-intl";

import { Field, FormErrors, Select, Text } from "@/components/profile/fields";
import { Alert, Button } from "@/components/ui";
import { BATCH_MODES } from "@/lib/batch-modes";
import type { Batch, BatchChanges, BatchInput, DeliverableCourse } from "@/lib/batches";
import type { Centre } from "@/lib/centres";
import { detailOf, fieldsOf } from "@/lib/http";

/**
 * One form for planning a batch and for changing one (Sprint 98, ADR-103): the same fields, the same
 * limits as `BatchIn`. **The course and the centre are chosen once**: changing either is a different
 * batch, and the learners who registered for this one did not choose that, so an edit shows them as
 * text and sends only the six things that can change.
 */
export function BatchForm({
  batch,
  courses,
  centres,
  inCentre = false,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  batch?: Batch;
  courses?: DeliverableCourse[];
  centres?: Centre[];
  /** A centre's own manager plans in their centre: there is no centre to choose. */
  inCentre?: boolean;
  pending: boolean;
  error: unknown;
  onSubmit: (body: BatchInput | BatchChanges) => void;
  onCancel?: () => void;
}) {
  const t = useTranslations("batches");
  const moves = batch !== undefined && batch.interested > 0 && batch.status === "published";
  return (
    <FormErrors fields={fieldsOf(error)}>
      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const s = (k: string) => String(f.get(k) ?? "").trim();
          const common = {
            label: s("label") || null,
            starts_on: batch && moves ? batch.starts_on : s("starts_on"),
            ends_on: batch && moves ? batch.ends_on : s("ends_on"),
            seats: Number(s("seats")),
            mode: s("mode") as (typeof BATCH_MODES)[number],
            schedule: s("schedule") || null,
            fee_inr: s("fee_inr") === "" ? null : Number(s("fee_inr")),
          };
          onSubmit(
            batch
              ? common
              : {
                  ...common,
                  course_slug: s("course_slug"),
                  centre_slug: inCentre ? null : s("centre_slug"),
                },
          );
        }}
      >
        {batch ? (
          <p className="text-sm text-muted sm:col-span-2">
            {t("fixedFor", { course: batch.course.title, centre: batch.centre.name })}
          </p>
        ) : (
          <>
            <Field label={t("course")} hint={t("courseHint")}>
              <Select name="course_slug" required defaultValue="">
                <option value="" disabled>
                  {t("chooseCourse")}
                </option>
                {(courses ?? []).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.own ? c.title : t("courseOption", { title: c.title, organisation: c.provider.name })}
                  </option>
                ))}
              </Select>
            </Field>
            {!inCentre && (
              <Field label={t("centre")} hint={t("centreHint")}>
                <Select name="centre_slug" required defaultValue="">
                  <option value="" disabled>
                    {t("chooseCentre")}
                  </option>
                  {(centres ?? []).map((c) => (
                    <option key={c.slug} value={c.slug}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
          </>
        )}
        <Field label={t("label")} hint={t("labelHint")} className="sm:col-span-2">
          <Text name="label" maxLength={120} defaultValue={batch?.label ?? ""} />
        </Field>
        <Field label={t("startsOn")}>
          <Text name="starts_on" type="date" required disabled={moves} defaultValue={batch?.starts_on ?? ""} />
        </Field>
        <Field label={t("endsOn")}>
          <Text name="ends_on" type="date" required disabled={moves} defaultValue={batch?.ends_on ?? ""} />
        </Field>
        {moves && (
          <Alert tone="warning" role={undefined} className="sm:col-span-2">
            {t("datesLocked")}
          </Alert>
        )}
        <Field label={t("seats")} hint={t("seatsHint")}>
          <Text name="seats" type="number" inputMode="numeric" min={1} max={5000} required defaultValue={batch?.seats ?? ""} />
        </Field>
        <Field label={t("modeLabel")}>
          <Select name="mode" defaultValue={batch?.mode ?? "in_person"}>
            {BATCH_MODES.map((m) => (
              <option key={m} value={m}>
                {t(`mode.${m}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("schedule")} hint={t("scheduleHint")}>
          <Text name="schedule" maxLength={200} defaultValue={batch?.schedule ?? ""} />
        </Field>
        <Field label={t("feeLabel")} hint={t("feeHint")}>
          <Text name="fee_inr" type="number" inputMode="numeric" min={0} max={10000000} defaultValue={batch?.fee_inr ?? ""} />
        </Field>
        {error != null && Object.keys(fieldsOf(error) ?? {}).length === 0 && (
          <Alert role="alert" className="sm:col-span-2">
            {detailOf(error) ?? t("failed")}
          </Alert>
        )}
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="submit" disabled={pending}>
            {batch ? t("saveChanges") : t("create")}
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              {t("back")}
            </Button>
          )}
        </div>
      </form>
    </FormErrors>
  );
}
