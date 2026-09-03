"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

type Kind = "skills" | "jobs" | "courses";

/** Real catalogue counts, fetched client-side so the static build never depends
 *  on the API being reachable. */
export function LiveCount({ kind }: { kind: Kind }) {
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

  return <span className="text-3xl font-semibold tabular-nums">{value ?? "—"}</span>;
}
