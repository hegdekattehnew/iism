import { fireEvent, screen } from "@testing-library/react-native";

import Careers from "../../app/careers";
import Gap from "../../app/gap/[id]";
import { account, api, failed, ok, resetWorld, roleHit, serve, setCourseBudget, suggestion, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

const gapOut = (extra: Record<string, unknown> = {}) => ({
  application_id: "a1",
  job: {
    slug: "ward-assistant-1",
    title: "Ward assistant 1",
    location_state: "Maharashtra",
    location_district: "Pune",
    employment_type: "full_time",
    tenant: { id: "t1", slug: "apollo", name: "Apollo Care", tenant_type: "employer", is_verified: true },
    removed: false,
  },
  status: "rejected",
  score: 41,
  coverage: 0.5,
  missing: [
    { skill_id: "s1", nos_code: "HSS/N1", name: "Bed making", importance: 2, is_mandatory: false },
    { skill_id: "s2", nos_code: "HSS/N2", name: "Infection control", importance: 5, is_mandatory: true },
  ],
  missing_mandatory: 1,
  level_shortfall: null,
  capped_by_mandatory: true,
  courses: [suggestion(1), suggestion(2, { within_budget: false })],
  ...extra,
});

describe("why not me", () => {
  beforeEach(() => {
    world.params = { id: "a1" };
  });

  it("names what the application was missing, required standards first, and the courses that teach it", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": ok(gapOut()) });
    await renderScreen(<Gap />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.getByText("Not selected")).toBeTruthy();
    expect(screen.getByText(/Based on your skills today/)).toBeTruthy();
    const needed = screen.getAllByText(/Infection control|Bed making/).map((n) => n.props.children);
    expect(needed.indexOf("Infection control")).toBeLessThan(needed.indexOf("Bed making"));
    expect(screen.getByText("Phlebotomy 1")).toBeTruthy();
    expect(screen.getByText("Over your budget")).toBeTruthy();
  });

  it("asks for this application, with no budget until there is one", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": ok(gapOut()) });
    await renderScreen(<Gap />);
    await screen.findByText("Ward assistant 1");
    const call = api.GET.mock.calls.find((c) => c[0] === "/me/applications/{application_id}/gap");
    expect(call?.[1]).toEqual({ params: { path: { application_id: "a1" }, query: {} } });
  });

  it("sends the budget the person set, as budget_inr", async () => {
    world.budget = 8000;
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": ok(gapOut()) });
    await renderScreen(<Gap />);
    await screen.findByText("Ward assistant 1");
    const call = api.GET.mock.calls.find((c) => c[0] === "/me/applications/{application_id}/gap");
    expect((call?.[1] as { params: { query: unknown } }).params.query).toEqual({ budget_inr: 8000 });
  });

  it("says nothing is missing when nothing is, and shows no courses to buy", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/applications/{application_id}/gap": ok(gapOut({ missing: [], missing_mandatory: 0, capped_by_mandatory: false, courses: [] })),
    });
    await renderScreen(<Gap />);
    expect(await screen.findByText(/Nothing is missing now/)).toBeTruthy();
    expect(screen.queryByLabelText("What would you pay for a course? (₹)")).toBeNull();
  });

  it("says the session ended on a 401", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": failed(401) });
    await renderScreen(<Gap />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("offers to try again on an outage", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": failed(500) });
    await renderScreen(<Gap />);
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("signed out asks to sign in and makes no request", async () => {
    world.signedIn = false;
    await renderScreen(<Gap />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
  });
});

describe("the budget field", () => {
  beforeEach(() => {
    world.params = { id: "a1" };
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications/{application_id}/gap": ok(gapOut()) });
  });

  it("sets a whole number of rupees", async () => {
    await renderScreen(<Gap />);
    await fireEvent.changeText(await screen.findByLabelText("What would you pay for a course? (₹)"), "12,000");
    await fireEvent.press(screen.getByRole("button", { name: "Show courses I can afford" }));
    expect(setCourseBudget).toHaveBeenCalledWith(12000);
  });

  it("refuses anything else and sets nothing", async () => {
    await renderScreen(<Gap />);
    await fireEvent.changeText(await screen.findByLabelText("What would you pay for a course? (₹)"), "cheap");
    await fireEvent.press(screen.getByRole("button", { name: "Show courses I can afford" }));
    expect(await screen.findByText("Enter a whole number of rupees.")).toBeTruthy();
    expect(setCourseBudget).not.toHaveBeenCalled();
  });

  it("can be cleared, and says it stays on this phone", async () => {
    world.budget = 5000;
    await renderScreen(<Gap />);
    expect(await screen.findByText(/Kept on this phone only/)).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Clear" }));
    expect(setCourseBudget).toHaveBeenCalledWith(null);
  });
});

const roleRef = (slug: string, name: string, level = 4) => ({ slug, qp_code: `HSS/${slug}`, job_role: name, nsqf_level: level, sector_name: "Healthcare" });
const step = (n: number, extra: Record<string, unknown> = {}) => ({
  role: roleRef(`senior-${n}`, `Senior attendant ${n}`, 5),
  basis: { shared_standards: 3, compulsory_count: 5, same_occupation: true, shared_nco: false },
  variants: 1,
  score: 72,
  coverage: 0.6,
  missing: [{ skill_id: "s9", nos_code: "HSS/N9", name: "Patient transfer", importance: 4, is_mandatory: true }],
  missing_mandatory: 1,
  level_shortfall: 1,
  experience_shortfall: null,
  courses: [suggestion(3)],
  entry: { qp_code: "HSS/Q5102", qp_name: "Senior Attendant", routes_total: 2, education_options: ["Class 12", "ITI"], lowest_experience_years: 2 },
  ...extra,
});
const ladder = (extra: Record<string, unknown> = {}) => ({
  anchor: roleRef("general-duty-assistant", "General Duty Assistant"),
  anchor_source: "chosen",
  needs_choice: false,
  has_skills: true,
  steps: [step(1), step(2)],
  ...extra,
});

describe("career paths", () => {
  it("shows the roles that build on the person's own, with the evidence for each step", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": ok(ladder()) });
    await renderScreen(<Careers />);
    expect(await screen.findByText("General Duty Assistant")).toBeTruthy();
    expect(screen.getByText("Senior attendant 1")).toBeTruthy();
    expect(screen.getAllByText("Shares 3 of 5 required standards with General Duty Assistant.").length).toBe(2);
    expect(screen.getAllByText("Same occupation").length).toBe(2);
    expect(screen.getByText(/not a promise of a job or a promotion/)).toBeTruthy();
    expect(screen.queryByText("We picked this from your profile. If it is not your role, change it.")).toBeNull();
  });

  it("says a guessed starting role is a guess", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": ok(ladder({ anchor_source: "guessed" })) });
    await renderScreen(<Careers />);
    expect(await screen.findByText("We picked this from your profile. If it is not your role, change it.")).toBeTruthy();
  });

  it("opens one step to what it would take, and closes it", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": ok(ladder()) });
    await renderScreen(<Careers />);
    await fireEvent.press(await screen.findByRole("button", { name: "What it would take: Senior attendant 1" }));
    expect(await screen.findAllByText("Patient transfer")).toBeTruthy();
    expect(screen.getAllByText("Phlebotomy 3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Education accepted: Class 12 · ITI").length).toBeGreaterThan(0);
    await fireEvent.press(screen.getByRole("button", { name: "Hide: Senior attendant 1" }));
    expect(screen.queryByText("Patient transfer")).toBeNull();
  });

  it("with no role to start from, asks for one and shows no steps", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/careers": ok(ladder({ anchor: null, anchor_source: "none", needs_choice: true, steps: [] })),
      "/roles/search": ok([roleHit(1)]),
    });
    await renderScreen(<Careers />);
    expect(await screen.findByLabelText("Your role")).toBeTruthy();
    expect(screen.queryByText("Senior attendant 1")).toBeNull();
  });

  it("choosing a role asks the server again for that role", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/careers": (init: unknown) =>
        ok((init as { params: { query: { role?: string } } }).params.query.role ? ladder() : ladder({ anchor: null, anchor_source: "none", needs_choice: true, steps: [] })),
      "/roles/search": ok([roleHit(1)]),
    });
    await renderScreen(<Careers />);
    await fireEvent.changeText(await screen.findByLabelText("Your role"), "ward boy");
    await fireEvent.press(await screen.findByRole("button", { name: /General Duty Assistant 1/ }));
    expect(await screen.findByText("Senior attendant 1")).toBeTruthy();
    const asked = api.GET.mock.calls.filter((c) => c[0] === "/me/careers").map((c) => (c[1] as { params: { query: unknown } }).params.query);
    expect(asked.at(-1)).toEqual({ role: "general-duty-assistant-1" });
  });

  it("with no skills yet, points at the profile instead of scoring nothing", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": ok(ladder({ has_skills: false })) });
    await renderScreen(<Careers />);
    await fireEvent.press(await screen.findByRole("button", { name: "Add my skills" }));
    const { router } = jest.requireActual("./mocks") as typeof import("./mocks");
    expect(router.push).toHaveBeenCalledWith("/profile");
  });

  it("says when the data names no further step", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": ok(ladder({ steps: [] })) });
    await renderScreen(<Careers />);
    expect(await screen.findByText(/found no further step from this role/)).toBeTruthy();
  });

  it("says the session ended on a 401", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/careers": failed(401) });
    await renderScreen(<Careers />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});
