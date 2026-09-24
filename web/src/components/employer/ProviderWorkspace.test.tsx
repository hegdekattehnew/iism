import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderWorkspace } from "@/components/employer/ProviderWorkspace";
import { org, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
// The real `@/lib/org`, with only the harness's `world`-driven pieces swapped
// in: this component's subject is `useOrgCourses` and `useOrgCourseMutations`.
vi.mock("@/lib/org", async () => ({
  ...(await vi.importActual<typeof import("@/lib/org")>("@/lib/org")),
  ...(await import("@/test/harness")).orgMock,
}));
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * The provider's half of the employer workspace, and the file whose docstring
 * described a signed-out branch it did not contain.
 *
 * It claimed the drift from `EmployerWorkspace` had been closed -- "there was
 * no signed-out branch at all, so a provider whose token had expired was told
 * they had no access to their own organisation". `isSignedOut` was never
 * imported here and `courses.isError` still answered "no access" to a 401.
 * A docstring that claims a fix is worse than one that admits the gap,
 * because it stops anybody looking.
 */

const course = (over: Record<string, unknown> = {}) => ({
  id: "c1",
  slug: "phlebotomy",
  title: "Phlebotomy",
  status: "draft",
  mode: "offline",
  duration_hours: 40,
  fee_inr: 2000,
  language: "hi",
  skills: [],
  tenant: { id: "t1", slug: "inst", name: "Inst", tenant_type: "course_provider" },
  ...over,
});

function serving(status: number | null, courses = [course()]) {
  GET.mockImplementation(async (path: string) => {
    if (status !== null)
      return { data: undefined, error: { detail: "no" }, response: { status } };
    if (path.includes("/interests")) return { data: [], error: undefined };
    if (path.includes("/courses")) return { data: courses, error: undefined };
    return { data: { memberships: [] }, error: undefined };
  });
}

beforeEach(() => {
  resetWorld();
  world.memberships = [org("inst", "course_provider", "Inst")];
  GET.mockReset();
  POST.mockReset();
  serving(null);
});

describe("ProviderWorkspace — 401 is not 403", () => {
  it("asks an expired session to sign in again", async () => {
    serving(401);
    renderUi(<ProviderWorkspace orgSlug="inst" />);

    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    // The exact wrong answer this branch exists to stop.
    expect(screen.queryByText(/do not have access/i)).toBeNull();
  });

  it("still says 'no access' to somebody who is genuinely not a member", async () => {
    // 404, because a tenant you are not a member of must be indistinguishable
    // from one that does not exist (ADR-038). That is not a session problem.
    serving(404);
    renderUi(<ProviderWorkspace orgSlug="inst" />);

    expect(await screen.findByText(/access/i)).toBeTruthy();
    expect(screen.queryByText(/Your session has expired/)).toBeNull();
  });
});

describe("ProviderWorkspace — saying why publishing failed", () => {
  it("shows the server's refusal rather than one fixed sentence", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "Add at least one standard this course teaches before publishing" },
      response: { status: 422 },
    });
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));

    expect(
      await screen.findByText(
        "Add at least one standard this course teaches before publishing",
      ),
    ).toBeTruthy();
  });

  it("sends an expired session to the sign-in panel, not the standards message", async () => {
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 401 } });
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});
