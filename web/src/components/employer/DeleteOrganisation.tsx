"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, Card, CardBody } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { isSignedOut } from "@/lib/http";

/**
 * Delete this organisation, and nothing else.
 *
 * **Reported as missing, and it was.** Somebody who signed up as a job seeker,
 * created an organisation to hire with and another to offer training, and then
 * wanted rid of only the first, found that the one control on offer deleted
 * their entire account. There was no route to delete an organisation at all,
 * and `leave` refuses the only owner on purpose -- so creating one was a single
 * request and undoing it was impossible.
 *
 * Three things make this safe enough to offer:
 *
 * - **The preview loads before the button appears**, because the part an owner
 *   does not think of is the applications. Those belong to somebody else.
 * - **The name has to be typed.** Not theatre: this is the only irreversible
 *   control in the product that destroys other people's records, and a
 *   `confirm()` is one stray Enter away from doing it.
 * - **It says what survives**, since the whole complaint was not knowing.
 */
export function DeleteOrganisation({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("orgSettings");
  const router = useRouter();
  const qc = useQueryClient();
  const [typed, setTyped] = useState("");
  const [failed, setFailed] = useState(false);

  const preview = useQuery({
    queryKey: ["org", orgSlug, "deletion"],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/deletion", {
        params: { path: { org_slug: orgSlug } },
      });
      // The status, not a message: 401 and 403 mean opposite things here and
      // the render below has to tell them apart.
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      setFailed(false);
      const { error } = await api.DELETE("/org/{org_slug}", {
        params: { path: { org_slug: orgSlug } },
      });
      if (error) throw new Error("delete failed");
    },
    onSuccess: async () => {
      // Everything cached about an organisation that no longer exists.
      await qc.invalidateQueries();
      router.push("/");
    },
    onError: () => setFailed(true),
  });

  if (preview.isPending) return null;
  // **401 and 403 are not the same refusal, and conflating them is what sent
  // an owner looking for a control that was not on the page.** A 403 means
  // this is not yours -- an admin is a member but not an owner -- and the
  // right answer is silence, because a button that always fails is worse than
  // no button (Sprint 14). A 401 means the fifteen-minute access token ran
  // out, which is not a permission problem at all and must say so.
  if (isSignedOut(preview.error)) return <SessionExpired variant="inline" />;
  if (preview.isError) return null;

  const counts = preview.data;
  const confirmed = typed.trim() === counts.name;

  return (
    <Card className="mt-8 border-danger-border">
      <CardBody>
        <h2 className="text-base font-semibold text-danger-text">{t("deleteHeading")}</h2>
        <p className="mt-2 text-sm text-muted">{t("deleteIntro")}</p>

        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">
          <li>{t("deleteJobs", { count: counts.jobs })}</li>
          <li>{t("deleteCourses", { count: counts.courses })}</li>
          {/* The part that belongs to other people, named separately. */}
          <li>{t("deleteApplications", { count: counts.applications })}</li>
          <li>{t("deleteInterests", { count: counts.course_interests })}</li>
          {counts.other_members > 0 && (
            <li>{t("deleteMembers", { count: counts.other_members })}</li>
          )}
        </ul>

        {/* The complaint was not knowing this. */}
        <Alert tone="info" role={undefined} className="mt-4">
          {t("deleteKeeps")}
        </Alert>

        <label className="mt-4 block text-sm">
          <span className="font-medium">{t("deleteConfirmLabel", { name: counts.name })}</span>
          <Text
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={counts.name}
            autoComplete="off"
          />
        </label>

        <div className="mt-4">
          <Button
            variant="danger"
            disabled={!confirmed || remove.isPending}
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? t("deleting") : t("deleteCta")}
          </Button>
        </div>
        {failed && <Alert className="mt-3">{t("deleteError")}</Alert>}
      </CardBody>
    </Card>
  );
}
