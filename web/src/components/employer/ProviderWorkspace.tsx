"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CourseEditor } from "@/components/employer/CourseEditor";
import { Badge, Button, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import {
  type CoursePayload,
  type OrgCourse,
  useOrgCourseMutations,
  useOrgCourses,
} from "@/lib/org";

/**
 * A training provider's own workspace.
 *
 * Until now a provider was handed the employer's workspace: a heading about
 * posting vacancies, a nav reading "Vacancies", and a primary button whose save
 * returned 403 into a mutation with no `onError` — so it did nothing at all and
 * said nothing about why.
 */
export function ProviderWorkspace({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("providerWorkspace");
  const te = useTranslations("employerWorkspace");
  const courses = useOrgCourses(orgSlug);
  const { create, update, setPublished } = useOrgCourseMutations(orgSlug);

  const [editing, setEditing] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  if (courses.isError) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{te("noAccess")}</p>
        </CardBody>
      </Card>
    );
  }

  const items: OrgCourse[] = courses.data ?? [];
  const current =
    editing && editing !== "new" ? items.find((c) => c.slug === editing) : null;

  const save = (payload: CoursePayload) => {
    setFailed(false);
    const done = () => setEditing(null);
    const onError = () => setFailed(true);
    if (editing === "new") create.mutate(payload, { onSuccess: done, onError });
    else if (current)
      update.mutate(
        { slug: current.slug, body: payload },
        { onSuccess: done, onError },
      );
  };

  if (editing) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold">
          {editing === "new" ? t("newCourse") : t("editCourse")}
        </h2>
        {failed && (
          <p className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
            {t("saveFailed")}
          </p>
        )}
        <CourseEditor
          course={current ?? null}
          saving={create.isPending || update.isPending}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("yourCourses")}</h2>
          <p className="mt-1 text-sm text-muted">{t("yourCoursesNote")}</p>
        </div>
        <Button onClick={() => setEditing("new")}>{t("newCourse")}</Button>
      </div>

      {failed && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
          {t("publishRefused")}
        </p>
      )}

      {courses.isPending && (
        <ul className="space-y-3">
          {[0, 1].map((i) => (
            <li key={i}>
              <Skeleton className="h-28 w-full rounded-xl" />
            </li>
          ))}
        </ul>
      )}

      {courses.isFetched && items.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm text-muted">{t("noCourses")}</p>
          </CardBody>
        </Card>
      )}

      <ul className="space-y-3">
        {items.map((course) => (
          <li key={course.slug}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-base font-semibold">
                      {course.title_en}
                    </h3>
                    <p className="mt-0.5 text-sm text-muted">
                      {t(`modes.${course.mode}`)}
                      {course.duration_hours != null &&
                        ` · ${t("hours", { hours: course.duration_hours })}`}
                      {course.nsqf_level != null &&
                        ` · ${t("nsqfLevelIs", { level: course.nsqf_level })}`}
                    </p>
                  </div>
                  {course.status === "published" ? (
                    <Badge tone="good">{te("published")}</Badge>
                  ) : (
                    <Badge tone="warn">{te("draft")}</Badge>
                  )}
                </div>

                <p className="mt-3 text-sm text-muted">
                  {t("teachesCount", { count: (course.skills ?? []).length })}
                </p>

                <div className="mt-4 flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    onClick={() => setEditing(course.slug)}
                    className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {te("edit")}
                  </button>
                  <button
                    type="button"
                    disabled={setPublished.isPending}
                    onClick={() => {
                      setFailed(false);
                      setPublished.mutate(
                        {
                          slug: course.slug,
                          published: course.status !== "published",
                        },
                        { onError: () => setFailed(true) },
                      );
                    }}
                    className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {course.status === "published"
                      ? te("unpublish")
                      : te("publish")}
                  </button>
                  {course.status === "published" && (
                    <Link
                      href={`/courses/${course.slug}`}
                      className="text-sm text-muted underline-offset-4 hover:underline"
                    >
                      {te("viewPublic")}
                    </Link>
                  )}
                </div>
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
