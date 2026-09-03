"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { SystemStatus } from "@/components/SystemStatus";
import { Button } from "@/components/ui";

/**
 * Sprint 1 verification surface, kept at the foot of the homepage and visually
 * separated so it never reads as part of the product. It stays until the
 * checks it performs move into real monitoring (ADR-019).
 */
export function DevPanel() {
  const t = useTranslations("dev");
  const ts = useTranslations("status");
  const [open, setOpen] = useState(true);

  return (
    <section className="border-t-2 border-dashed border-border-token bg-surface-muted px-5 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="inline-flex items-center rounded-md border border-border-token bg-surface px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
              {t("title")}
            </p>
            <h2 className="mt-2 text-xl font-bold tracking-tight">{ts("title")}</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">{t("subtitle")}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setOpen((v) => !v)}>
            {open ? t("hide") : t("show")}
          </Button>
        </div>

        {open && <SystemStatus />}
      </div>
    </section>
  );
}
