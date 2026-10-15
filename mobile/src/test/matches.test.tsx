import { fireEvent, screen } from "@testing-library/react-native";

import Matches from "../../app/(tabs)/matches";
import MatchDetail from "../../app/match/[slug]";
import {
  account,
  api,
  failed,
  job,
  matchItem,
  ok,
  resetWorld,
  router,
  serve,
  suggestion,
  world,
} from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const page = (items: unknown[], has_skills = true) => ({ items, total: items.length, has_skills });

describe("the matches tab for somebody signed out", () => {
  it("shows the way in and makes no request that could only answer 401", async () => {
    await renderScreen(<Matches />);
    await settle();
    expect(screen.getByText("Your matches")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Sign in" }));
    expect(router.push).toHaveBeenCalledWith("/sign-in");
    expect(api.GET).not.toHaveBeenCalled();
  });
});

describe("the matches tab for an organisation that signed in on a phone", () => {
  it("says this is the job seeker's app and asks for no matches", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account("organisation")) });
    await renderScreen(<Matches />);
    expect(await screen.findByText(/This app is for job seekers/)).toBeTruthy();
    expect(api.GET.mock.calls.map((c) => c[0])).toEqual(["/auth/me"]);
  });
});

describe("the matches tab for a job seeker", () => {
  beforeEach(() => {
    world.signedIn = true;
  });

  it("lists the jobs with their score, best first, and opens one", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/matches": ok(page([matchItem(1), matchItem(2, { locality: 2 })])),
    });
    await renderScreen(<Matches />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.getByText("79% match")).toBeTruthy();
    expect(screen.getByText("78% match")).toBeTruthy();
    expect(screen.getByText("In your district")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Ward assistant 2" }));
    expect(router.push).toHaveBeenCalledWith("/match/ward-assistant-2");
  });

  it("says what limits a capped match in words, not a bare 'Required'", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/matches": ok(page([matchItem(1, { capped_by_mandatory: true, missing_mandatory: 2 })])),
    });
    await renderScreen(<Matches />);
    expect(await screen.findByText("2 mandatory standards missing")).toBeTruthy();
    expect(screen.queryByText("Required")).toBeNull();
  });

  it("says no skills yet is a different thing from no matches, and points at the profile", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches": ok(page([], false)) });
    await renderScreen(<Matches />);
    expect(await screen.findByText(/Add a few skills to your profile/)).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Go to my profile" }));
    expect(router.push).toHaveBeenCalledWith("/profile");
  });

  it("says nothing matches yet when there are skills and no match", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches": ok(page([], true)) });
    await renderScreen(<Matches />);
    expect(await screen.findByText(/Nothing matches your skills yet/)).toBeTruthy();
  });

  it("shows a placeholder, never an empty list, until the first answer", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches": new Promise(() => undefined) });
    await renderScreen(<Matches />);
    await settle();
    expect(screen.queryByText(/Nothing matches your skills yet/)).toBeNull();
    expect(screen.queryByText(/Add a few skills/)).toBeNull();
    expect(screen.getAllByLabelText("Loading").length).toBeGreaterThan(0);
  });

  it("says the session ended on a 401, which is not a failure to load", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches": failed(401) });
    await renderScreen(<Matches />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    expect(screen.queryByText(/could not load/i)).toBeNull();
  });

  it("offers a retry when it could not load", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches": failed(500) });
    await renderScreen(<Matches />);
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("one match opened", () => {
  const open = (extra: Record<string, unknown> = {}) => {
    world.signedIn = true;
    world.params = { slug: "ward-assistant-1" };
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/matches/{slug}": ok({ ...matchItem(1), courses: [suggestion(1)], entry: null, ...extra }),
      "/jobs/{slug}": ok(job(1)),
      "/me/applications": ok([]),
      "/me/saved-jobs": ok([]),
    });
  };

  it("shows the score, the coverage, and what is needed with the required standards first", async () => {
    open();
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText("79% match")).toBeTruthy();
    expect(screen.getByText(/75% of what this role requires/)).toBeTruthy();
    expect(screen.getByText("✓ Hand hygiene")).toBeTruthy();
    const needs = screen.getAllByText(/^(Bed making|Infection control)$/).map((n) => n.props.children);
    expect(needs).toEqual(["Infection control", "Bed making"]);
  });

  it("explains a cap, an experience shortfall and a level shortfall in the scorer's own fields", async () => {
    open({ capped_by_mandatory: true, missing_mandatory: 2, experience_shortfall: 2, level_shortfall: 1 });
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText(/One required standard is missing, which limits this match/)).toBeTruthy();
    expect(screen.getByText("2 mandatory standards missing")).toBeTruthy();
    expect(screen.getByText(/2 years short of the experience/)).toBeTruthy();
    expect(screen.getByText(/NSQF 3 against the 4 this role asks for/)).toBeTruthy();
  });

  it("lists the courses that close the gap with where, when and what they cost", async () => {
    open();
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText("Phlebotomy 1")).toBeTruthy();
    expect(screen.getByText(/Pune, Maharashtra · Starts 2 Nov 2026 · ₹12,500 · 120 hours · 5 seats left/)).toBeTruthy();
    expect(screen.getByText("In your district")).toBeTruthy();
    expect(screen.getByText("Closes 1 of 2 of your gap")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Phlebotomy 1" }));
    expect(router.push).toHaveBeenCalledWith("/course/phlebotomy-1");
  });

  it("labels a started, full or faraway course instead of hiding it", async () => {
    open({ courses: [suggestion(1, { started: true, full: true, reach: "elsewhere" })] });
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText("Elsewhere")).toBeTruthy();
    expect(screen.getByText("Already started")).toBeTruthy();
    expect(screen.getAllByText("Full").length).toBeGreaterThan(0);
  });

  it("says no course covers the gap when none does", async () => {
    open({ courses: [] });
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText(/No course on the platform covers this gap yet/)).toBeTruthy();
  });

  it("shows how to become qualified when the vacancy maps to a qualification", async () => {
    open({
      entry: { qp_code: "HSS/Q5101", qp_name: "General Duty Assistant", routes_total: 3, education_options: ["Class 10"], lowest_experience_years: 1 },
    });
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText(/This role maps to General Duty Assistant \(HSS\/Q5101\)/)).toBeTruthy();
    expect(screen.getByText(/3 ways in/)).toBeTruthy();
  });

  it("offers to apply, naming nobody else's rules: the panel is the one on the vacancy page", async () => {
    open();
    await renderScreen(<MatchDetail />);
    expect(await screen.findByRole("button", { name: "Apply for this job" })).toBeTruthy();
  });

  it("makes no request for somebody signed out", async () => {
    world.params = { slug: "ward-assistant-1" };
    await renderScreen(<MatchDetail />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("says the session ended on a 401", async () => {
    world.signedIn = true;
    world.params = { slug: "ward-assistant-1" };
    serve(api.GET, { "/auth/me": ok(account()), "/me/matches/{slug}": failed(401), "/jobs/{slug}": ok(job(1)) });
    await renderScreen(<MatchDetail />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});
