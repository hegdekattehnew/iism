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
    if (path.includes("/batches/overview"))
      return {
        data: {
          drafts: 1,
          starting_soon: 4,
          running: 0,
          unfilled_seats: 6,
          unfilled_batches: 1,
          unavailable: 0,
          upcoming: [],
        },
        error: undefined,
      };
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

/** Sprint 73, UI-15: a course row has one primary action, Edit beside it, and the rest behind "More". */
describe("ProviderWorkspace: a row's actions", () => {
  const row = async () => (await screen.findByText("Phlebotomy")).closest("li")!;

  it("makes the interested learners the primary action of a live course", async () => {
    serving(null, [course({ status: "published" })]);
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    const li = await row();
    const more = li.querySelector("details")!;
    expect(more.hasAttribute("open")).toBe(false);
    const learners = screen.getByRole("link", { name: /Interested learners/ });
    expect(more.contains(learners)).toBe(false);
    expect(learners.getAttribute("href")).toBe("/employer/inst/courses/phlebotomy/interests");
    expect(more.contains(screen.getByRole("button", { name: "Unpublish" }))).toBe(true);
    expect(more.contains(screen.getByRole("link", { name: "View the public posting" }))).toBe(true);
  });

  it("makes Publish the primary action of a draft and moves the learners under More", async () => {
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    const li = await row();
    const more = li.querySelector("details")!;
    expect(more.contains(screen.getByRole("button", { name: "Publish" }))).toBe(false);
    expect(more.contains(screen.getByRole("link", { name: /Interested learners/ }))).toBe(true);
  });

  it("holds every action to the 44 px floor by using the button sizes", async () => {
    serving(null, [course({ status: "published" })]);
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    const li = await row();
    for (const control of li.querySelectorAll("button, a[href]")) {
      expect(control.className, control.textContent ?? "").toMatch(/min-h-11/);
    }
  });
});

/** Sprint 88, BL-19.18: a course's state is a word with a shape and a tone, and what it teaches an icon chip. */
describe("ProviderWorkspace -- the look of a course's state", () => {
  it.each([
    [{ status: "draft" }, "Draft", "bg-warning-surface"],
    [{ status: "published" }, "Published", "bg-success-surface"],
    [{ status: "published", taken_down_at: "2026-10-01T00:00:00Z", takedown_reason: "x" }, "Removed", "bg-danger-surface"],
  ])("draws %j as %s on %s, with a shape", async (over, word, token) => {
    serving(null, [course(over)]);
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    const chip = (await screen.findByText(word, { selector: "span" })) as HTMLElement;
    expect(chip.className).toContain(token);
    expect(chip.querySelector("svg")).toBeTruthy();
  });

  it("shows how many standards it teaches as an icon chip", async () => {
    serving(null, [course({ skills: [{ skill_slug: "a", name: "A", level_taught: 3 }] })]);
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    const chip = await screen.findByText("Teaches 1 standard");
    expect(chip.querySelector("svg")).toBeTruthy();
  });

  it("draws the three states in three different shapes", async () => {
    const shapes: string[] = [];
    for (const [over, word] of [
      [{ status: "draft" }, "Draft"],
      [{ status: "published" }, "Published"],
      [{ status: "published", taken_down_at: "2026-10-01T00:00:00Z", takedown_reason: "x" }, "Removed"],
    ] as const) {
      serving(null, [course(over)]);
      const { unmount } = renderUi(<ProviderWorkspace orgSlug="inst" />);
      shapes.push(((await screen.findByText(word, { selector: "span" })) as HTMLElement).querySelector("svg")!.innerHTML);
      unmount();
    }
    expect(new Set(shapes).size).toBe(3);
  });
});

describe("ProviderWorkspace — a delivering organisation leads with its batches (Sprint 99)", () => {
  it("shows the figures above the courses for an organisation that delivers", async () => {
    const m = org("inst", "course_provider", "Inst");
    m.tenant.delivers_training = true;
    world.memberships = [m];
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    expect(await screen.findByText("Starting this week")).toBeTruthy();
    const courses = await screen.findByRole("heading", { name: "Your courses" });
    const figures = screen.getByText("Starting this week").compareDocumentPosition(courses);
    expect(figures & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("asks for nothing and shows nothing of the kind to an organisation that only sells", async () => {
    renderUi(<ProviderWorkspace orgSlug="inst" />);
    await screen.findByRole("heading", { name: "Your courses" });
    expect(screen.queryByText("Starting this week")).toBeNull();
    expect(GET.mock.calls.some((c) => String(c[0]).includes("/batches/overview"))).toBe(false);
  });
});
