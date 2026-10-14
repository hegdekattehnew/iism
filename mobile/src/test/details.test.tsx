import { fireEvent, screen } from "@testing-library/react-native";

import CourseDetail from "../../app/course/[slug]";
import JobDetail from "../../app/job/[slug]";
import SkillDetail from "../../app/skill/[slug]";
import { api, course, failed, job, ok, resetWorld, router, skill, world } from "./mocks";
import { renderScreen } from "./harness";

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
    expect(screen.getByText("Useful")).toBeTruthy();
    expect(api.GET.mock.calls[0][0]).toBe("/jobs/{slug}");
  });

  it("states the terms in the shared words, with Indian grouping", async () => {
    world.params = { slug: "ward-assistant-1" };
    api.GET.mockResolvedValue(ok(job(1)));
    await renderScreen(<JobDetail />);
    expect(await screen.findByText("1–3 years")).toBeTruthy();
    expect(screen.getByText("₹2,40,000–3,60,000 per year")).toBeTruthy();
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
