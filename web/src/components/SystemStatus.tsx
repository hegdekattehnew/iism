"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api, type ComponentHealth } from "@/lib/api";

const POLL_MS = 5000;
const SETTLED = ["complete", "not_found"];

function Dot({ up }: { up: boolean }) {
  return (
    <span className="relative flex h-2.5 w-2.5" aria-hidden>
      {up && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
      )}
      <span
        className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
          up ? "bg-emerald-500" : "bg-rose-500"
        }`}
      />
    </span>
  );
}

function Card({ label, component }: { label: string; component: ComponentHealth | null }) {
  const t = useTranslations("components");
  const up = component?.status === "up";

  return (
    <div className="rounded-xl border border-border-token bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-muted">{label}</span>
        <Dot up={up} />
      </div>
      <p
        className={`mt-2 text-lg font-semibold ${
          up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
        }`}
      >
        {up ? t("up") : t("down")}
      </p>
      {component?.latency_ms != null && (
        <p className="mt-0.5 text-xs text-muted">{component.latency_ms} ms</p>
      )}
      {component?.detail && (
        <p className="mt-1 truncate text-xs text-muted" title={component.detail}>
          {component.detail}
        </p>
      )}
    </div>
  );
}

export function SystemStatus() {
  const t = useTranslations("status");
  const tc = useTranslations("components");
  const tt = useTranslations("task");
  const td = useTranslations("data");

  const [jobId, setJobId] = useState<string | null>(null);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/health/deep");
      if (error || !data) throw new Error("unreachable");
      return data;
    },
    refetchInterval: POLL_MS,
    // A status board must keep polling while the tab is in the background;
    // without this TanStack pauses the interval whenever the tab is hidden.
    refetchIntervalInBackground: true,
  });

  const skills = useQuery({
    queryKey: ["skill-count"],
    queryFn: async () => (await api.GET("/skills/count")).data ?? null,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: true,
  });

  // Polls only while the job is unsettled; TanStack stops on its own.
  const job = useQuery({
    queryKey: ["task", jobId],
    enabled: jobId !== null,
    queryFn: async () => {
      const { data } = await api.GET("/tasks/{job_id}", {
        params: { path: { job_id: jobId as string } },
      });
      return data ?? null;
    },
    refetchInterval: (q) =>
      q.state.data && SETTLED.includes(q.state.data.status) ? false : 700,
    refetchIntervalInBackground: true,
  });

  const enqueue = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/tasks/ping", {
        params: { query: { note: "from-the-status-page" } },
      });
      if (error || !data) throw new Error("enqueue failed");
      return data.job_id;
    },
    onSuccess: setJobId,
  });

  const find = (name: string) =>
    health.data?.components.find((c) => c.name === name) ?? null;

  const apiUp = health.isSuccess;
  const allUp = apiUp && health.data?.status === "up";
  // Derived, not stored: a second state for "busy" would need an effect to sync.
  const busy =
    enqueue.isPending ||
    (jobId !== null && !SETTLED.includes(job.data?.status ?? ""));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Dot up={!!allUp} />
          <span
            className={`text-sm font-semibold ${
              allUp
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-rose-700 dark:text-rose-400"
            }`}
          >
            {health.isPending
              ? t("checking")
              : !apiUp
                ? t("unreachable")
                : allUp
                  ? t("allUp")
                  : t("someDown")}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          {health.dataUpdatedAt > 0 && (
            <span>
              {t("lastChecked")}:{" "}
              {new Date(health.dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <Button variant="secondary" size="sm" onClick={() => void health.refetch()}>
            {t("refresh")}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card
          label={tc("api")}
          component={
            health.isPending
              ? null
              : {
                  name: "api",
                  status: apiUp ? "up" : "down",
                  latency_ms: null,
                  detail: health.data ? `v${health.data.version}` : null,
                }
          }
        />
        <Card label={tc("postgres")} component={find("postgres")} />
        <Card label={tc("redis")} component={find("redis")} />
        <Card label={tc("worker")} component={find("worker")} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-border-token bg-surface p-5">
          <h3 className="text-base font-semibold">{tt("title")}</h3>
          <p className="mt-1 text-sm leading-relaxed text-muted">{tt("description")}</p>
          <Button
            className="mt-4"
            onClick={() => enqueue.mutate()}
            disabled={busy || !allUp}
          >
            {busy ? tt("running") : tt("run")}
          </Button>

          {jobId && (
            <dl className="mt-4 space-y-1.5 rounded-lg bg-surface-muted p-3 text-xs">
              <div className="flex gap-2">
                <dt className="text-muted">{tt("jobId")}:</dt>
                <dd className="font-mono">{jobId.slice(0, 12)}…</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-muted">{tt("statusLabel")}:</dt>
                <dd className="font-medium">
                  {job.data?.status
                    ? tt.has(job.data.status)
                      ? tt(job.data.status)
                      : job.data.status
                    : tt("queued")}
                </dd>
              </div>
              {job.data?.result?.completed_at != null && (
                <div className="flex gap-2">
                  <dt className="text-muted">{tt("completedAt")}:</dt>
                  <dd className="font-mono">{String(job.data.result.completed_at)}</dd>
                </div>
              )}
            </dl>
          )}
        </section>

        <section className="rounded-xl border border-border-token bg-surface p-5">
          <h3 className="text-base font-semibold">{td("title")}</h3>
          <p className="mt-4 text-3xl font-semibold tabular-nums">
            {skills.data?.count ?? "—"}
          </p>
          <p className="mt-0.5 text-sm text-muted">{td("skillsSeeded")}</p>
          <p className="mt-3 text-xs text-muted">{td("emptyNote")}</p>
        </section>
      </div>

      {health.data && (
        <p className="text-xs text-muted">
          {t("environment")}: <span className="font-mono">{health.data.environment}</span>
          {" · "}
          {t("version")}: <span className="font-mono">{health.data.version}</span>
        </p>
      )}
    </div>
  );
}
