import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LiveCount } from "@/components/LiveCount";
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
 * The homepage panel that was reported as "not updating".
 *
 * It was updating, and the number was right. It counted **open** vacancies,
 * and the seed closes one on every run, so publishing a twenty-first moved the
 * figure 19 -> 20 and the employer who had just published could not reconcile
 * it. The panel now leads with how many have been posted and names the live
 * figure underneath.
 *
 * `BrowsePanels` cannot be tested here -- it is `async` and uses
 * `getTranslations` from `next-intl/server` -- which is a further reason the
 * label and the conditional line belong in this component. Until now nothing
 * rendered it at all.
 */

function answer({ posted = 21, open = 20, courses = 50, skills = 21303 } = {}) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/marketplace/counts")
      return { data: { jobs_posted: posted, jobs_open: open, courses } };
    if (path === "/skills/count") return { data: { count: skills } };
    return { data: undefined };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  answer();
});

describe("the jobs panel", () => {
  it("leads with how many have been posted, not with how many are open", async () => {
    renderUi(<LiveCount kind="jobs" />);
    expect(await screen.findByText("21")).toBeTruthy();
    expect(screen.getByText("vacancies posted")).toBeTruthy();
  });

  it("names the live figure underneath when some have closed", async () => {
    // The number a visitor will actually find at /jobs, said out loud rather
    // than left as a discrepancy for them to discover by clicking Browse.
    renderUi(<LiveCount kind="jobs" />);
    expect(await screen.findByText("20 open right now")).toBeTruthy();
  });

  it("says nothing about open vacancies when none have closed", async () => {
    // The branch nobody sees while developing: `scripts/seed_marketplace.py`
    // closes one vacancy on every run, so a seeded database always shows the
    // two-line form and this one rots unwatched.
    answer({ posted: 21, open: 21 });
    renderUi(<LiveCount kind="jobs" />);
    expect(await screen.findByText("21")).toBeTruthy();
    expect(screen.queryByText(/open right now/)).toBeNull();
  });

  it("says nothing about open vacancies before the figures arrive", async () => {
    // Comparing two `undefined`s would hide the line for the right reason by
    // accident; this pins that it is hidden for the stated one.
    GET.mockImplementation(() => new Promise(() => {}));
    renderUi(<LiveCount kind="jobs" />);
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.queryByText(/open right now/)).toBeNull();
  });

  it("groups both figures the Indian way, as the band above them does", async () => {
    answer({ posted: 238370, open: 238369 });
    renderUi(<LiveCount kind="jobs" />);
    expect(await screen.findByText("2,38,370")).toBeTruthy();
    expect(screen.getByText("2,38,369 open right now")).toBeTruthy();
  });
});

describe("the other two panels", () => {
  it("does not describe the course catalogue as vacancies", async () => {
    renderUi(<LiveCount kind="courses" />);
    expect(await screen.findByText("50")).toBeTruthy();
    expect(screen.getByText("in the catalogue")).toBeTruthy();
    expect(screen.queryByText(/vacanc/i)).toBeNull();
    expect(screen.queryByText(/open right now/)).toBeNull();
  });

  // `renderUi` throws on MISSING_MESSAGE, so this is what turns the
  // `countLabel` -> `${kind}CountLabel` split into a failing test rather than
  // a homepage whose label reads "browse.jobsCountLabel".
  it.each(["jobs", "courses", "skills"] as const)(
    "has a label for the %s panel",
    async (kind) => {
      renderUi(<LiveCount kind={kind} />);
      expect(
        await screen.findByText(/in the catalogue|vacancies posted/),
      ).toBeTruthy();
    },
  );

  it("renders a dash rather than a zero when the API is unreachable", async () => {
    // A zero here would be a lie about the corpus -- the rule `StatsBand`
    // states and the reason both are fetched client-side.
    GET.mockResolvedValue({ data: undefined });
    renderUi(<LiveCount kind="skills" />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(screen.getByText("—")).toBeTruthy();
  });
});
