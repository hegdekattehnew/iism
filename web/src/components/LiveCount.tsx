"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import { api } from "@/lib/api";

type Kind = "skills" | "jobs" | "courses";

/** Real catalogue counts, fetched client-side so the static build never depends
 *  on the API being reachable. */
export function LiveCount({ kind }: { kind: Kind }) {
  const locale = useLocale();
  const skills = useQuery({
    queryKey: ["skill-count"],
    queryFn: async () => (await api.GET("/skills/count")).data ?? null,
    enabled: kind === "skills",
  });

  const marketplace = useQuery({
    queryKey: ["marketplace-counts"],
    queryFn: async () => (await api.GET("/marketplace/counts")).data ?? null,
    enabled: kind !== "skills",
  });

  const value =
    kind === "skills"
      ? skills.data?.count
      : kind === "jobs"
        ? marketplace.data?.jobs
        : marketplace.data?.courses;

  // Indian grouping, the same rule `StatsBand` applies -- 21,303 not 21303.
  // The two sit within a screen of each other on the homepage, and an
  // unformatted number beside a formatted one reads as a different kind of
  // number rather than a larger one.
  const shown =
    value == null
      ? "—"
      : new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(
          value,
        );

  return <span className="text-3xl font-semibold tabular-nums">{shown}</span>;
}
