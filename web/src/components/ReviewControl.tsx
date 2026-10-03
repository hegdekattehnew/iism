"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Area } from "@/components/profile/fields";
import { Alert, Button } from "@/components/ui";
import { detailOf } from "@/lib/http";

/**
 * Rate the other side of a finished gig, 1 to 5 with an optional note.
 *
 * One control for both directions: the employer rating the worker and the
 * worker rating the employer are the same act, and what differs is only which
 * endpoint `submit` calls and what `prompt` asks. The server fixes the
 * direction by route and never accepts it from the caller.
 *
 * The caller decides whether to render it at all, from the payload's
 * `reviewed` flag -- the API answers a second review with a 409, so a form that
 * stays on screen after submitting is a form that fails the next press.
 */
export function ReviewControl({
  prompt,
  submit,
  onSaved,
}: {
  prompt: string;
  submit: (review: { rating: number; comment: string | null }) => Promise<void>;
  onSaved: () => void | Promise<void>;
}) {
  const t = useTranslations("reviews");
  const name = useId();
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");

  const save = useMutation({
    mutationFn: (review: { rating: number; comment: string | null }) => submit(review),
    onSuccess: onSaved,
  });

  return (
    <form
      className="mt-4 space-y-3 rounded-lg bg-surface-muted p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (rating === null) return;
        save.mutate({ rating, comment: comment.trim() || null });
      }}
    >
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{prompt}</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t("ratingLabel")}>
          {[1, 2, 3, 4, 5].map((n) => (
            <label
              key={n}
              className={`flex h-11 w-11 cursor-pointer items-center justify-center rounded-lg border text-sm font-semibold ${
                rating === n
                  ? "border-brand bg-brand text-brand-contrast"
                  : "border-input-border bg-surface"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={n}
                checked={rating === n}
                onChange={() => setRating(n)}
                className="sr-only"
                aria-label={t("stars", { count: n })}
              />
              {n}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="block text-sm">
        <span className="font-medium">{t("commentLabel")}</span>
        <Area
          name="comment"
          value={comment}
          maxLength={1000}
          onChange={(event) => setComment(event.target.value)}
        />
      </label>

      {save.isError && (
        <Alert role="alert">{detailOf(save.error) ?? t("failed")}</Alert>
      )}

      <Button type="submit" size="sm" disabled={rating === null || save.isPending}>
        {save.isPending ? t("saving") : t("submit")}
      </Button>
    </form>
  );
}
