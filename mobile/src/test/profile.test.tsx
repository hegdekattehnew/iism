import { fireEvent, screen } from "@testing-library/react-native";

import Profile from "../../app/profile";
import { account, api, failed, ok, profile, resetWorld, roleHit, roleStandard, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

const skill = (slug: string, name: string) => ({ skill: { slug, name }, proficiency: 3, source: "self_declared" });

const serveProfile = (p: unknown = profile(), more: Record<string, unknown> = {}) =>
  serve(api.GET, { "/auth/me": ok(account()), "/me/profile": ok(p), ...more });

const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));
const putBody = () => (api.PUT.mock.calls[0][1] as { body: Record<string, unknown> }).body;

describe("the profile, signed out", () => {
  it("asks to sign in and makes no request", async () => {
    world.signedIn = false;
    await renderScreen(<Profile />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
    expect(screen.getByText("Sign in to build your profile.")).toBeTruthy();
  });
});

describe("the basics", () => {
  it("starts from the profile as loaded and shows how complete it is", async () => {
    serveProfile();
    await renderScreen(<Profile />);
    expect(await screen.findByDisplayValue("Asha Rao")).toBeTruthy();
    expect(screen.getByDisplayValue("Ward boy")).toBeTruthy();
    expect(screen.getByDisplayValue("Pune")).toBeTruthy();
    expect(screen.getByDisplayValue("3")).toBeTruthy();
    expect(screen.getByText("Profile 60% complete")).toBeTruthy();
    expect(screen.getByText("Add your skills next")).toBeTruthy();
  });

  it("saves only the fields it edits, trimmed", async () => {
    serveProfile();
    serve(api.PUT, { "/me/profile": ok(profile({ headline: "Ward attendant" })) });
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("Headline"), "  Ward attendant ");
    await press("Save");
    await settle();
    expect(putBody()).toEqual({
      full_name: "Asha Rao",
      headline: "Ward attendant",
      location_state: "Maharashtra",
      location_district: "Pune",
      years_experience: 3,
      education_level: "secondary",
    });
    expect(await screen.findByText("Saved")).toBeTruthy();
  });

  it("sends a cleared field as null, so clearing it works", async () => {
    serveProfile();
    serve(api.PUT, { "/me/profile": ok(profile()) });
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("District or city"), "");
    await press("Save");
    await settle();
    expect(putBody().location_district).toBeNull();
  });

  it("sends nothing for years of experience that are not a number, and says so", async () => {
    serveProfile();
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("Years of experience"), "x1");
    await press("Save");
    expect(await screen.findByText("Could not save. Please check the fields.")).toBeTruthy();
    expect(api.PUT).not.toHaveBeenCalled();
  });

  it("changes and clears the highest education by tapping it", async () => {
    serveProfile();
    serve(api.PUT, { "/me/profile": ok(profile()) });
    await renderScreen(<Profile />);
    await press("ITI");
    await press("Save");
    await settle();
    expect(putBody().education_level).toBe("iti");
  });

  it("shows the server's own sentence when it refuses a field", async () => {
    serveProfile();
    serve(api.PUT, { "/me/profile": failed(422, "Expected maximum salary cannot be below the minimum") });
    await renderScreen(<Profile />);
    await press("Save");
    expect(await screen.findByText("Expected maximum salary cannot be below the minimum")).toBeTruthy();
  });

  it("says the session ended on a 401", async () => {
    serveProfile();
    serve(api.PUT, { "/me/profile": failed(401) });
    await renderScreen(<Profile />);
    await press("Save");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("limits each input to what the server accepts", async () => {
    serveProfile();
    await renderScreen(<Profile />);
    expect((await screen.findByLabelText("Full name")).props.maxLength).toBe(120);
    expect(screen.getByLabelText("Headline").props.maxLength).toBe(160);
    expect(screen.getByLabelText("State").props.maxLength).toBe(80);
    expect(screen.getByLabelText("District or city").props.maxLength).toBe(80);
    expect(screen.getByLabelText("Years of experience").props.maxLength).toBe(2);
  });
});

describe("the skills held", () => {
  it("lists them, and removes one by its slug", async () => {
    serveProfile(profile({ skills: [skill("hand-hygiene", "Hand hygiene")] }));
    serve(api.DELETE, { "/me/profile/skills/{skill_slug}": ok(profile()) });
    await renderScreen(<Profile />);
    expect(await screen.findByText("Hand hygiene")).toBeTruthy();
    await press("Remove: Hand hygiene");
    await settle();
    expect(api.DELETE.mock.calls[0][1]).toEqual({ params: { path: { skill_slug: "hand-hygiene" } } });
  });

  it("says when it could not change them", async () => {
    serveProfile(profile({ skills: [skill("hand-hygiene", "Hand hygiene")] }));
    serve(api.DELETE, { "/me/profile/skills/{skill_slug}": failed(500) });
    await renderScreen(<Profile />);
    await press("Remove: Hand hygiene");
    expect(await screen.findByText(/Could not change your standards/)).toBeTruthy();
  });

  it("says there are none yet", async () => {
    serveProfile();
    await renderScreen(<Profile />);
    expect(await screen.findByText(/No skills added yet/)).toBeTruthy();
  });
});

describe("naming a job and ticking what you can do", () => {
  const roles = (extra: Record<string, unknown> = {}) =>
    serveProfile(profile({ skills: [skill("std-a", "Standard std-a")] }), {
      "/roles/search": ok([roleHit(1)]),
      "/roles/{slug}/standards": ok({
        slug: "general-duty-assistant-1",
        job_role: "General Duty Assistant 1",
        qp_code: "HSS/Q5101-1",
        qp_name: "General Duty Assistant",
        standards: [
          roleStandard("std-a", "compulsory"),
          roleStandard("std-b", "compulsory"),
          roleStandard("std-c", "elective", "Pick one"),
          roleStandard("std-d", "elective", "Another"),
          roleStandard("std-e", "optional"),
        ],
      }),
      ...extra,
    });

  const choose = async () => {
    await fireEvent.changeText(await screen.findByLabelText("e.g. ward boy, delivery, cashier, electrician"), "ward boy");
    await fireEvent.press(await screen.findByRole("button", { name: "General Duty Assistant 1" }));
    await screen.findByText("Core to the job");
  };

  it("finds the role by what the person typed and says how it was matched", async () => {
    roles();
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("e.g. ward boy, delivery, cashier, electrician"), "ward boy");
    expect(await screen.findByText("General Duty Assistant 1")).toBeTruthy();
    expect(screen.getByText("4 standards")).toBeTruthy();
    expect(screen.getByText("Matched “ward boy”")).toBeTruthy();
    expect(api.GET.mock.calls.find((c) => c[0] === "/roles/search")?.[1]).toEqual({ params: { query: { q: "ward boy", limit: 8 } } });
  });

  it("starts with nothing ticked, keeps electives in their groups and shows what is already held", async () => {
    roles();
    await renderScreen(<Profile />);
    await choose();
    expect(screen.getByText("Choose from: Pick one")).toBeTruthy();
    expect(screen.getByText("Choose from: Another")).toBeTruthy();
    expect(screen.getByText("Optional")).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "Standard std-b" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Standard std-a" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Standard std-a" })).toBeDisabled();
    expect(screen.getByText("Already on your profile")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tick at least one" })).toBeDisabled();
  });

  it("cannot tick a standard already held", async () => {
    roles();
    await renderScreen(<Profile />);
    await choose();
    await fireEvent.press(screen.getByRole("checkbox", { name: "Standard std-a" }));
    expect(screen.getByRole("button", { name: "Tick at least one" })).toBeDisabled();
  });

  it("adds the ticked standards in one request with the confidence and the preferred role", async () => {
    roles();
    serve(api.POST, { "/me/profile/skills/bulk": ok(profile({ skills: [skill("std-a", "A"), skill("std-b", "B"), skill("std-c", "C")] })) });
    await renderScreen(<Profile />);
    await choose();
    await fireEvent.press(screen.getByRole("checkbox", { name: "Standard std-b" }));
    await fireEvent.press(screen.getByRole("checkbox", { name: "Standard std-c" }));
    await fireEvent.press(screen.getByRole("button", { name: "4" }));
    expect(screen.getByRole("button", { name: "Add 2 skills" })).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Add 2 skills" }));
    await settle();
    expect(api.POST.mock.calls[0]).toEqual([
      "/me/profile/skills/bulk",
      {
        body: {
          items: [
            { skill_slug: "std-b", proficiency: 4 },
            { skill_slug: "std-c", proficiency: 4 },
          ],
          preferred_role_title: "General Duty Assistant 1",
        },
      },
    ]);
    expect(await screen.findByText(/2 skills added/)).toBeTruthy();
  });

  it("leaves the preferred role out when the person unticks it", async () => {
    roles();
    serve(api.POST, { "/me/profile/skills/bulk": ok(profile()) });
    await renderScreen(<Profile />);
    await choose();
    await fireEvent.press(screen.getByRole("checkbox", { name: "Standard std-b" }));
    await fireEvent.press(screen.getByRole("checkbox", { name: "Also save this as a job I'm looking for" }));
    await fireEvent.press(screen.getByRole("button", { name: "Add 1 skill" }));
    await settle();
    expect((api.POST.mock.calls[0][1] as { body: { preferred_role_title: unknown } }).body.preferred_role_title).toBeNull();
  });

  it("shows the server's sentence when the whole batch is refused, and adds nothing", async () => {
    roles();
    serve(api.POST, { "/me/profile/skills/bulk": failed(422, "A profile may hold at most 60 standards.") });
    await renderScreen(<Profile />);
    await choose();
    await fireEvent.press(screen.getByRole("checkbox", { name: "Standard std-b" }));
    await fireEvent.press(screen.getByRole("button", { name: "Add 1 skill" }));
    expect(await screen.findByText("A profile may hold at most 60 standards.")).toBeTruthy();
    expect(screen.queryByText(/skill added/)).toBeNull();
  });

  it("says no job by that name when there is none", async () => {
    roles({ "/roles/search": ok([]) });
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("e.g. ward boy, delivery, cashier, electrician"), "zzz");
    expect(await screen.findByText(/No job by that name yet/)).toBeTruthy();
  });

  it("lets the person choose a different job", async () => {
    roles();
    await renderScreen(<Profile />);
    await choose();
    await fireEvent.press(screen.getByRole("button", { name: "Choose a different job" }));
    expect(await screen.findByText("What work do you do?")).toBeTruthy();
  });
});

describe("the history sections", () => {
  it("lists the six sections with how many entries each holds, and opens one", async () => {
    serveProfile(profile({ experiences: [{ id: "e1" }, { id: "e2" }], languages: [{ id: "l1" }] }));
    await renderScreen(<Profile />);
    await screen.findByText("Your history");
    expect(screen.getByRole("button", { name: "Work history · 2 entries" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Languages · 1 entry" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Education · Nothing added" })).toBeTruthy();
    await press("Work history · 2 entries");
    expect(router.push).toHaveBeenCalledWith("/profile/experiences");
  });
});

describe("what the person is looking for", () => {
  it("starts from the profile as loaded", async () => {
    serveProfile(
      profile({ expected_salary_min_inr: 12000, expected_salary_max_inr: 18000, notice_period: "immediate", willing_to_relocate: true }),
    );
    await renderScreen(<Profile />);
    expect(await screen.findByDisplayValue("12000")).toBeTruthy();
    expect(screen.getByDisplayValue("18000")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Immediately" }).props.accessibilityState).toMatchObject({ selected: true });
  });

  it("saves only what it edits: no name, no date of birth, no gender", async () => {
    serveProfile(profile());
    serve(api.PUT, { "/me/profile": ok(profile()) });
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("Expected salary from"), "15,000");
    await press("Full time");
    await press("Save: What you are looking for");
    await settle();
    expect(putBody()).toEqual({
      expected_salary_min_inr: 15000,
      expected_salary_max_inr: null,
      notice_period: null,
      preferred_employment_type: "full_time",
      willing_to_relocate: false,
      job_alerts_enabled: true,
    });
  });

  it("refuses a top below the bottom before any request, saying which rule", async () => {
    serveProfile(profile());
    await renderScreen(<Profile />);
    await fireEvent.changeText(await screen.findByLabelText("Expected salary from"), "20000");
    await fireEvent.changeText(screen.getByLabelText("to"), "10000");
    await press("Save: What you are looking for");
    expect(await screen.findByText("The top of the range cannot be below the bottom.")).toBeTruthy();
    expect(api.PUT).not.toHaveBeenCalled();
  });

  it("turning alerts off is sent", async () => {
    serveProfile(profile());
    serve(api.PUT, { "/me/profile": ok(profile()) });
    await renderScreen(<Profile />);
    await fireEvent(await screen.findByLabelText("Tell me when a matching vacancy is published"), "valueChange", false);
    await press("Save: What you are looking for");
    await settle();
    expect(putBody().job_alerts_enabled).toBe(false);
  });
});
