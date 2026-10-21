"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { InterestCard } from "@/components/cards/InterestCard";
import { ButtonLink, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { BookOpenIcon } from "@/components/ui/icons";

/** Which courses the learner has asked about, and where each stands. */
export function InterestList() {
  const t = useTranslations("courseInterest");
  const { data, isPending, isError } = useQuery({
    queryKey: ["me", "course-interests"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/course-interests");
      if (error || !data) throw new Error("interests failed");
      return data;
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-32 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) {
    return (
      <EmptyState
        icon={BookOpenIcon}
        title={t("empty")}
        action={<ButtonLink href="/courses">{t("emptyCta")}</ButtonLink>}
        className="mt-8"
      />
    );
  }

  return (
    <ul className="mt-8 space-y-4">
      {data.map((interest) => (
        <li key={interest.id}>
          <InterestCard interest={interest} />
        </li>
      ))}
    </ul>
  );
}
