import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SkillRelated } from "@/components/SkillRelated";
import messages from "@/messages/en.json";
import { resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));
vi.mock("next-intl/server", async () => {
  const intl = await import("next-intl");
  const en = (await import("@/messages/en.json")).default;
  return {
    getTranslations: async (ns: string) => intl.createTranslator({ locale: "en", messages: en, namespace: ns as never }),
  };
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 85, BL-19.15: the two links under a standard's lists were 22 px tall. */
describe("SkillRelated", () => {
  it("makes the link to every job and to every course a 44 px target", async () => {
    GET.mockImplementation(async (path: string) =>
      path.endsWith("/jobs")
        ? { data: [{ slug: "gda", title: "General Duty Assistant", tenant: { name: "Apollo Care" } }] }
        : { data: [{ slug: "gda-course", title: "GDA certificate", tenant: { name: "NSDC Academy" } }] },
    );
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        {await SkillRelated({ slug: "hand-hygiene" })}
      </NextIntlClientProvider>,
    );
    const jobs = screen.getByRole("link", { name: /See all jobs needing it/ });
    const courses = screen.getByRole("link", { name: /See all courses teaching it/ });
    expect(jobs.getAttribute("href")).toBe("/jobs?skill=hand-hygiene");
    expect(courses.getAttribute("href")).toBe("/courses?skill=hand-hygiene");
    expect(jobs.className).toContain("min-h-11");
    expect(courses.className).toContain("min-h-11");
  });
});
