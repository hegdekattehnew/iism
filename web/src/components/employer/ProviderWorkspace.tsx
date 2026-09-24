"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CourseEditor } from "@/components/employer/CourseEditor";
import { Alert, Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { SessionExpired } from "@/components/SessionExpired";
import { detailOf, isSignedOut } from "@/lib/http";
import { Link } from "@/i18n/navigation";
import {
  type CoursePayload,
  type OrgCourse,
  useMemberships,
  useOrgCourseMutations,
  useOrgCourses,
  useOrgInterests,
} from "@/lib/org";

/**
 * A training provider's own workspace.
 *
 * Until now a provider was handed the employer's workspace: a heading about
 * posting vacancies, a nav reading "Vacancies", and a primary button whose save
 * returned 403 into a mutation with no `onError` — so it did nothing at all and
 * said nothing about why.
 *
 * Kept deliberately parallel to `EmployerWorkspace`, and the two ways it had
 * drifted from that sibling were both invisible until read side by side: a
 * single `failed` flag served the save-failure banner *and* the publish-refused
 * one, so cancelling out of the editor after a failed save showed "publish
 * refused" for something that had never been attempted; and there was no
 * signed-out branch at all, so a provider whose token had expired was told they
 * had no access to their own organisation rather than being asked to sign in.
 *
 * **That second paragraph described a fix this file did not contain.** It was
 * written as though done; `isSignedOut` was never imported here and
 * `courses.isError` still answered "no access" to a 401. The branch below is
 * the real one. A docstring that claims a fix is worse than one that admits
 * the gap, because it stops anybody looking.
 */
export function ProviderWorkspace({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("providerWorkspace");
  const te = useTranslations("employerWorkspace");
  const me = useMemberships();
  const courses = useOrgCourses(orgSlug);
  // One request for the whole list, joined by slug -- not one per card.
  const interest = useOrgInterests(orgSlug);
  const interestBySlug = new Map(
    (interest.data ?? []).map((row) => [row.course_slug, row.live]),
  );
  const { create, update, setPublished } = useOrgCourseMutations(orgSlug);

  // null = closed, "new" = creating, otherwise the slug being edited.
  const [editing, setEditing] = useState<string | null>(null);
  // Two states, not one: they are shown on different screens and mean
  // different things.
  // What the server said when publishing was refused -- its own sentence,
  // not one fixed line about missing standards shown for every failure.
  const [actionFailed, setActionFailed] = useState<string | true | null>(null);
  // The server's own words, like the employer's workspace.
  const [saveFailed, setSaveFailed] = useState<string | true | null>(null);
  // A 401 from a mutation: the session expires while the page is already open.
  const [signedOut, setSignedOut] = useState(false);

  if (me.isError) {
    return (
      <Card>
        <CardBody>
          {/* The provider's own wording: `employerWorkspace` says "manage
              your vacancies", which is the exact confusion Sprint 14 removed.
              And `/signin` directly -- sign-in is one door now, and routing a
              training provider through an employer-named path is the old
              assumption wearing a redirect. */}
          <p className="text-sm text-muted">{t("signInPrompt")}</p>
          <ButtonLink href="/signin" className="mt-4">
            {t("signIn")}
          </ButtonLink>
        </CardBody>
      </Card>
    );
  }

  if (signedOut || isSignedOut(courses.error) || isSignedOut(me.error))
    return <SessionExpired />;

  if (courses.isError) {
    // A 404 here means "not a member of this organisation", which is
    // deliberately indistinguishable from "no such organisation". A 401 is
    // handled above: it means signed out, not unwelcome.
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
    setSaveFailed(null);
    const done = () => setEditing(null);
    const onError = (e: unknown) => setSaveFailed(detailOf(e) ?? true);
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
        {saveFailed && (
          <Alert role="alert">
            {typeof saveFailed === "string" ? saveFailed : t("saveFailed")}
          </Alert>
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

      {actionFailed && (
        <Alert role="alert">
          {/* The server's own words -- "Add at least one standard this course
              teaches before publishing" -- when it sent any. */}
          {typeof actionFailed === "string" ? actionFailed : t("actionFailed")}
        </Alert>
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
                      {course.title}
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
                      setActionFailed(null);
                      setPublished.mutate(
                        {
                          slug: course.slug,
                          published: course.status !== "published",
                        },
                        {
                          onError: (e) => {
                            if (isSignedOut(e)) {
                              setSignedOut(true);
                              return;
                            }
                            setActionFailed(detailOf(e) ?? true);
                          },
                        },
                      );
                    }}
                    className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {course.status === "published"
                      ? te("unpublish")
                      : te("publish")}
                  </button>
                  <Link
                    href={`/employer/${orgSlug}/courses/${course.slug}/interests`}
                    className="text-sm font-medium text-brand underline-offset-4 hover:underline"
                  >
                    {t("interestedLearners", {
                      count: interestBySlug.get(course.slug) ?? 0,
                    })}
                  </Link>
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
