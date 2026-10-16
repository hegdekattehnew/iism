import { fireEvent, screen, within } from "@testing-library/react-native";

import CourseDetail from "../../app/course/[slug]";
import JobDetail from "../../app/job/[slug]";
import SkillDetail from "../../app/skill/[slug]";
import { api, course, failed, job, ok, resetWorld, router, skill, tenant, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const standard = (n: number, mandatory: boolean, importance: number) => ({
  skill: skill(n),
  is_mandatory: mandatory,
  importance,
});

describe("a vacancy", () => {
  it("shows the standards it requires, the ones that gate a hire first", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(
      ok(job(1, { skills: [standard(1, false, 5), standard(2, true, 2), standard(3, true, 4)] })),
    );
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");

    const names = screen.getAllByText(/^Hand hygiene \d$/).map((n) => n.props.children);
    expect(names).toEqual(["Hand hygiene 3", "Hand hygiene 2", "Hand hygiene 1"]);
    expect(screen.getAllByText("Must have")).toHaveLength(2);
    // The chip says what gates a hire; "importance 5 of 5" was a number nobody could act on (UI-09).
    expect(screen.queryByText(/Importance/)).toBeNull();
    expect(screen.queryByText("Useful")).toBeNull();
    expect(api.GET.mock.calls[0][0]).toBe("/jobs/{slug}");
  });

  it("collapses a standard listed twice, and sets the generic ones aside", async () => {
    world.params = { slug: "ward-assistant-1" };
    const named = (slug: string, name: string, mandatory: boolean) => ({
      skill: { ...skill(1), slug, name },
      is_mandatory: mandatory,
      importance: 3,
    });
    api.GET.mockResolvedValue(
      ok(
        job(1, {
          skills: [
            named("a", "MAINTAIN HYGIENE", false),
            named("b", "Maintain hygiene", true),
            named("c", "Employability Skills (60 Hours)", true),
          ],
        }),
      ),
    );
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    expect(screen.getAllByText("Maintain hygiene")).toHaveLength(1);
    // Generic entries are behind a button, not in the list a seeker scans.
    expect(screen.queryByText("Employability Skills (60 Hours)")).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "Also covered (1)" }));
    expect(screen.getByText("Employability Skills (60 Hours)")).toBeTruthy();
  });

  it("states the terms in the shared words, with Indian grouping", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("1–3 years")).toBeTruthy();
    // What people say it is (a month), then what was posted (a year) beneath it (UI-05).
    expect(screen.getByText("About ₹20,000–30,000 a month")).toBeTruthy();
    expect(screen.getByText("₹2,40,000–3,60,000 per year")).toBeTruthy();
  });

  it("keeps a gig's posted figure and shows no yearly line under it", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { employment_type: "gig", salary_min_inr: 5000, salary_max_inr: 8000 })));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("₹5,000–8,000 as posted")).toBeTruthy();
    expect(screen.queryByText(/a month/)).toBeNull();
    expect(screen.queryByText(/per year/)).toBeNull();
  });

  it("states whether the employer is verified, and what nobody may ask for", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("Verified employer")).toBeTruthy();
    expect(screen.getByText(/Never pay to apply for a job/)).toBeTruthy();
    expect(screen.queryByText("Not yet verified")).toBeNull();
  });

  it("says 'not yet verified' here, on the page that can explain it", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { tenant: { ...tenant, is_verified: false } })));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("Not yet verified")).toBeTruthy();
    expect(screen.queryByText("Verified employer")).toBeNull();
  });

  it("says how soon it closes when that is near", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { closes_at: new Date(Date.now() + 3 * 86_400_000 - 1000).toISOString() })));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("Closes in 3 days")).toBeTruthy();
  });

  it("says how long ago the vacancy was posted, and nothing when it has no date", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { published_at: new Date(Date.now() - 5 * 86_400_000 - 1000).toISOString() })));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("Posted 5 days ago")).toBeTruthy();
  });

  it("keeps Apply in a bar under the content, not inside the scrolling part (UI-08)", async () => {
    world.params = { slug: "ward-assistant-1" };
    world.signedIn = false;
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    // Apply is in the bar and not in the part that scrolls.
    expect(within(screen.getByTestId("screen-footer")).getByText("Sign in to apply")).toBeTruthy();
    expect(within(screen.getByTestId("screen-content")).queryByText("Sign in to apply")).toBeNull();
  });

  it("has no bar for an organisation-only account, which cannot apply, not an empty strip", async () => {
    world.params = { slug: "ward-assistant-1" };
    world.signedIn = true;
    api.GET.mockImplementation(async (path: string) =>
      path === "/auth/me"
        ? ok({ memberships: [{ role: "owner", tenant: { slug: "acme", name: "Acme", tenant_type: "employer" } }] })
        : path === "/me/applications" || path === "/me/saved-jobs"
          ? ok([])
          : ok(job(1)),
    );
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    await settle();
    expect(screen.queryByTestId("screen-footer")).toBeNull();
  });

  it("has the bar, with Apply and Save side by side, for a job seeker", async () => {
    world.params = { slug: "ward-assistant-1" };
    world.signedIn = true;
    api.GET.mockImplementation(async (path: string) =>
      path === "/auth/me"
        ? ok({ memberships: [{ role: "owner", tenant: { slug: "me", name: "Me", tenant_type: "personal" } }] })
        : path === "/me/applications" || path === "/me/saved-jobs"
          ? ok([])
          : ok(job(1)),
    );
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    const bar = await screen.findByTestId("screen-footer");
    expect(within(bar).getByRole("button", { name: "Apply for this job" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Save for later" })).toBeTruthy();
  });

  it("says a closed vacancy is closed", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { is_open: false })));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText(/This vacancy is closed/)).toBeTruthy();
  });

  it("asks a signed-out visitor to sign in to see how they match, and nobody else", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    await fireEvent.press(screen.getByRole("button", { name: "Sign in" }));
    expect(router.push).toHaveBeenCalledWith("/sign-in");
  });

  it("does not offer it to somebody already signed in", async () => {
    world.params = { slug: "ward-assistant-1" };
    world.signedIn = true;
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    await screen.findByText("Ward assistant 1");
    expect(screen.queryByText(/Sign in to see how well you match/)).toBeNull();
  });

  it("says a missing vacancy does not exist, and an outage is not that", async () => {
    world.params = { slug: "gone" };
    api.GET.mockResolvedValue(failed(404, "Job not found"));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("This page does not exist")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("says an outage could not load, with a way to retry", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(failed(503, "Database unavailable"));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("This page could not load")).toBeTruthy();
    expect(screen.queryByText("This page does not exist")).toBeNull();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("opens a required standard", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1, { skills: [standard(7, true, 3)] })));
    await renderScreen(<JobDetail />);
    await fireEvent.press(await screen.findByRole("button", { name: "Hand hygiene 7" }));
    expect(router.push).toHaveBeenCalledWith("/skill/hand-hygiene-7");
  });
});

describe("a course", () => {
  it("gives the fee, length, place, the next intake in full and the places left", async () => {
    world.params = { slug: "phlebotomy-1" };
    api.GET.mockResolvedValue(ok(course(1, { seats_left: 3, skills: [{ skill: skill(1), level_taught: 4 }] })));
    await renderScreen(<CourseDetail />);
    expect(await screen.findByText("₹12,500")).toBeTruthy();
    expect(screen.getByText("120 hours")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("Starts 2 November 2026")).toBeTruthy();
    expect(screen.getByText("3 seats left")).toBeTruthy();
    expect(screen.getByText("to level 4")).toBeTruthy();
  });

  it("says full at no seats", async () => {
    world.params = { slug: "phlebotomy-1" };
    api.GET.mockResolvedValue(ok(course(1, { seats_left: 0 })));
    await renderScreen(<CourseDetail />);
    expect(await screen.findByText("Full")).toBeTruthy();
  });

  it("says nothing about places when the provider did not say", async () => {
    world.params = { slug: "phlebotomy-1" };
    api.GET.mockResolvedValue(ok(course(1, { seats_left: null })));
    await renderScreen(<CourseDetail />);
    await screen.findByText("Phlebotomy 1");
    expect(screen.queryByText("Places")).toBeNull();
  });

  it("says when the start date is not stated, and when an in-person course has no place", async () => {
    world.params = { slug: "phlebotomy-1" };
    api.GET.mockResolvedValue(
      ok(course(1, { starts_on: null, location_state: null, location_district: null })),
    );
    await renderScreen(<CourseDetail />);
    expect(await screen.findByText("Start date not stated")).toBeTruthy();
    expect(screen.getByText("Place not stated")).toBeTruthy();
  });

  it("shows a Hindi month in Hindi", async () => {
    world.params = { slug: "phlebotomy-1" };
    world.locale = "hi";
    api.GET.mockResolvedValue(ok(course(1)));
    await renderScreen(<CourseDetail />, "hi");
    await screen.findByText("Phlebotomy 1");
    expect(screen.getByText(/2 नवंबर 2026/)).toBeTruthy();
  });
});

describe("a standard", () => {
  it("shows its code, where it comes from, and the jobs and courses that use it", async () => {
    world.params = { slug: "hand-hygiene-1" };
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/skills/{slug}") return ok(skill(1, { description: "Clean hands, every time." }));
      if (path === "/skills/{slug}/jobs") return ok([job(5)]);
      return ok([course(6)]);
    });
    await renderScreen(<SkillDetail />);
    expect(await screen.findByText("Hand hygiene 1")).toBeTruthy();
    expect(screen.getByText("NOS code: HSS/N1")).toBeTruthy();
    expect(screen.getByText("Clean hands, every time.")).toBeTruthy();
    await fireEvent.press(await screen.findByRole("button", { name: "Ward assistant 5" }));
    expect(router.push).toHaveBeenCalledWith("/job/ward-assistant-5");
    await fireEvent.press(screen.getByRole("button", { name: "Phlebotomy 6" }));
    expect(router.push).toHaveBeenCalledWith("/course/phlebotomy-6");
  });

  it("says no job lists it when none does", async () => {
    world.params = { slug: "hand-hygiene-1" };
    api.GET.mockImplementation(async (path: string) => (path === "/skills/{slug}" ? ok(skill(1)) : ok([])));
    await renderScreen(<SkillDetail />);
    expect(await screen.findByText("No jobs currently list this skill.")).toBeTruthy();
  });
});
