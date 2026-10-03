import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InterestList } from "@/components/InterestList";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

/**
 * `enrolled` shipped in the API in Sprint 38 and this screen kept a
 * hand-written three-value status type, cast onto the server's value. An
 * enrolled learner got no colour and no wording -- a raw message key. The
 * harness throws on a missing key, so rendering every status is the guard.
 */
const interest = (status: string, id = status) => ({
  id,
  status,
  registered_at: "2026-09-14T09:00:00Z",
  course: {
    slug: `course-${id}`,
    title: `Course ${id}`,
    tenant: { id: "t1", slug: "skillbridge", name: "SkillBridge", tenant_type: "course_provider" },
  },
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("InterestList", () => {
  it("names every status in words, enrolled included", async () => {
    GET.mockResolvedValue({
      data: [
        interest("registered"),
        interest("contacted"),
        interest("enrolled"),
        interest("withdrawn"),
      ],
      error: undefined,
    });
    renderUi(<InterestList />);

    expect(await screen.findByText("Registered")).toBeTruthy();
    expect(screen.getByText("They got in touch")).toBeTruthy();
    expect(screen.getByText("Enrolled")).toBeTruthy();
    expect(screen.getByText("Withdrawn")).toBeTruthy();
  });
});
