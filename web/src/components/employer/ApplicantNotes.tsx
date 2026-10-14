"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { ApiError, detailOf, readDetail } from "@/lib/http";
import { NOTES_MAX } from "@/lib/hiring";

/**
 * Your own note on one applicant (Sprint 60, BL-14.8).
 *
 * Private to the organisation: the candidate never sees it in the product. It is still personal
 * data about them held here, so a person may ask for a copy of what is held about them, and the
 * form says so: write what you would stand behind.
 */
export function ApplicantNotes({
  org,
  jobSlug,
  applicationId,
  notes,
  onSaved,
}: {
  org: string;
  jobSlug: string;
  applicationId: string;
  notes: string;
  onSaved: () => unknown;
}) {
  const t = useTranslations("employerInbox");
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? notes;

  const save = useMutation({
    mutationFn: async (value: string) => {
      const { error, response } = await api.PUT(
        "/org/{org_slug}/jobs/{job_slug}/applications/{application_id}/notes",
        {
          params: {
            path: {
              org_slug: org,
              job_slug: jobSlug,
              application_id: applicationId,
            },
          },
          body: { notes: value.trim() || undefined },
        },
      );
      const status = response.status;
      if (error) throw new ApiError(status, readDetail(error));
    },
    onSuccess: async () => {
      await onSaved();
      setDraft(null);
    },
  });

  return (
    <div className="mt-4 border-t border-border-token pt-4">
      <label
        className="block text-sm font-medium"
        htmlFor={`notes-${applicationId}`}
      >
        {t("notesLabel")}
      </label>
      <textarea
        id={`notes-${applicationId}`}
        name="notes"
        rows={2}
        maxLength={NOTES_MAX}
        value={shown}
        onChange={(event) => setDraft(event.target.value)}
        className="mt-1 w-full rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
      />
      <p className="mt-1 text-xs text-muted">{t("notesHint")}</p>
      <div className="mt-2 flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={draft === null || draft === notes || save.isPending}
          onClick={() => save.mutate(draft ?? "")}
        >
          {save.isPending ? t("notesSaving") : t("notesSave")}
        </Button>
        {save.isError && (
          <span role="alert" className="text-sm text-danger-text">
            {detailOf(save.error) ?? t("notesFailed")}
          </span>
        )}
      </div>
    </div>
  );
}
