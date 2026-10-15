import { fireEvent, screen } from "@testing-library/react-native";

import Section from "../../app/profile/[section]";
import { account, api, failed, ok, profile, resetWorld, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

const worked = {
  id: "e1",
  employer_name: "Apollo Care",
  role_title: "Ward attendant",
  location: "Nagpur",
  started_on: "2019-04-15",
  ended_on: "2021-09-30",
  is_current: false,
  description: "Night shifts",
};

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
  world.params = { section: "experiences" };
});

const withProfile = (extra: Record<string, unknown> = {}) =>
  serve(api.GET, { "/auth/me": ok(account()), "/me/profile": ok(profile(extra)), "/me/matches": ok({ items: [], total: 0, has_skills: true }) });
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));
const body = (mock: jest.Mock) => (mock.mock.calls[0][1] as { body: Record<string, unknown> }).body;

describe("a history section", () => {
  it("shows the entries as the role, the employer and the months worked", async () => {
    withProfile({ experiences: [worked] });
    await renderScreen(<Section />);
    expect(await screen.findByText("Ward attendant")).toBeTruthy();
    expect(screen.getByText("Apollo Care")).toBeTruthy();
    expect(screen.getByText("Apr 2019 - Sep 2021")).toBeTruthy();
  });

  it("says when there is nothing yet", async () => {
    withProfile({ experiences: [] });
    await renderScreen(<Section />);
    expect(await screen.findByText("Nothing added yet.")).toBeTruthy();
  });

  it("signed out asks to sign in and makes no request", async () => {
    world.signedIn = false;
    await renderScreen(<Section />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("an unknown section reaches nothing (a mistyped or hostile link)", async () => {
    world.params = { section: "skills" };
    withProfile();
    await renderScreen(<Section />);
    expect(await screen.findByText("There is no such section.")).toBeTruthy();
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
    expect(api.POST).not.toHaveBeenCalled();
  });
});

describe("adding", () => {
  it("checks the form first, naming what is missing beside the field, and sends nothing", async () => {
    withProfile({ experiences: [] });
    await renderScreen(<Section />);
    await press("Add");
    await press("Save");
    expect((await screen.findAllByText("This is needed.")).length).toBe(3);
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("sends what was typed, the start as the first of the month", async () => {
    withProfile({ experiences: [] });
    serve(api.POST, { "/me/profile/{collection}": ok(profile({ experiences: [worked] })) });
    await renderScreen(<Section />);
    await press("Add");
    await fireEvent.changeText(await screen.findByLabelText("Employer"), " Apollo Care ");
    await fireEvent.changeText(screen.getByLabelText("Role"), "Ward attendant");
    const [startMonth] = screen.getAllByLabelText("Month (1 to 12)");
    const [startYear] = screen.getAllByLabelText("Year");
    await fireEvent.changeText(startMonth, "4");
    await fireEvent.changeText(startYear, "2019");
    await press("Save");
    await settle();
    expect(api.POST.mock.calls[0][0]).toBe("/me/profile/{collection}");
    expect((api.POST.mock.calls[0][1] as { params: unknown }).params).toEqual({ path: { collection: "experiences" } });
    expect(body(api.POST)).toMatchObject({
      employer_name: "Apollo Care",
      role_title: "Ward attendant",
      started_on: "2019-04-01",
      ended_on: null,
      is_current: false,
    });
    // The form closes and the list returns.
    expect(await screen.findByText("Apr 2019 - Sep 2021")).toBeTruthy();
  });

  it("shows the server's own sentence when it still refuses, and keeps what was typed", async () => {
    withProfile({ experiences: [] });
    serve(api.POST, { "/me/profile/{collection}": failed(422, "Role title is too long for this employer") });
    await renderScreen(<Section />);
    await press("Add");
    await fireEvent.changeText(await screen.findByLabelText("Employer"), "Apollo Care");
    await fireEvent.changeText(screen.getByLabelText("Role"), "Ward attendant");
    await fireEvent.changeText(screen.getAllByLabelText("Month (1 to 12)")[0], "4");
    await fireEvent.changeText(screen.getAllByLabelText("Year")[0], "2019");
    await press("Save");
    expect(await screen.findByText("Role title is too long for this employer")).toBeTruthy();
    expect(screen.getByDisplayValue("Apollo Care")).toBeTruthy();
  });

  it("says the session ended on a 401, not that the entry was wrong", async () => {
    withProfile({ experiences: [] });
    serve(api.POST, { "/me/profile/{collection}": failed(401) });
    await renderScreen(<Section />);
    await press("Add");
    await fireEvent.changeText(await screen.findByLabelText("Employer"), "A");
    await fireEvent.changeText(screen.getByLabelText("Role"), "B");
    await fireEvent.changeText(screen.getAllByLabelText("Month (1 to 12)")[0], "4");
    await fireEvent.changeText(screen.getAllByLabelText("Year")[0], "2019");
    await press("Save");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("'I work here now' hides the end date, as the website does", async () => {
    withProfile({ experiences: [] });
    await renderScreen(<Section />);
    await press("Add");
    expect((await screen.findAllByLabelText("Month (1 to 12)")).length).toBe(2);
    await fireEvent(screen.getByLabelText("I work here now"), "valueChange", true);
    expect(screen.getAllByLabelText("Month (1 to 12)").length).toBe(1);
  });
});

describe("changing and removing", () => {
  it("an edit that leaves the dates alone sends back the exact dates the website recorded", async () => {
    withProfile({ experiences: [worked] });
    serve(api.PUT, { "/me/profile/{collection}/{entry_id}": ok(profile({ experiences: [worked] })) });
    await renderScreen(<Section />);
    await press("Edit: Ward attendant");
    await fireEvent.changeText(await screen.findByLabelText("What you did"), "Day shifts");
    await press("Save");
    await settle();
    expect((api.PUT.mock.calls[0][1] as { params: unknown }).params).toEqual({
      path: { collection: "experiences", entry_id: "e1" },
    });
    expect(body(api.PUT)).toMatchObject({ started_on: "2019-04-15", ended_on: "2021-09-30", description: "Day shifts" });
  });

  it("asks before it removes, and removes that entry", async () => {
    withProfile({ experiences: [worked] });
    serve(api.DELETE, { "/me/profile/{collection}/{entry_id}": ok(profile({ experiences: [] })) });
    await renderScreen(<Section />);
    await press("Remove: Ward attendant");
    expect(api.DELETE).not.toHaveBeenCalled();
    await press("Yes, remove");
    await settle();
    expect((api.DELETE.mock.calls[0][1] as { params: unknown }).params).toEqual({
      path: { collection: "experiences", entry_id: "e1" },
    });
  });

  it("cancelling the question removes nothing", async () => {
    withProfile({ experiences: [worked] });
    await renderScreen(<Section />);
    await press("Remove: Ward attendant");
    await press("Cancel");
    expect(api.DELETE).not.toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: "Remove: Ward attendant" })).toBeTruthy();
  });

  it("says why a removal failed, in the server's words", async () => {
    withProfile({ experiences: [worked] });
    serve(api.DELETE, { "/me/profile/{collection}/{entry_id}": failed(404, "That entry no longer exists") });
    await renderScreen(<Section />);
    await press("Remove: Ward attendant");
    await press("Yes, remove");
    expect(await screen.findByText("That entry no longer exists")).toBeTruthy();
  });
});

describe("the other sections", () => {
  it("languages start conversational, reading and writing, and send the choice", async () => {
    world.params = { section: "languages" };
    withProfile({ languages: [] });
    serve(api.POST, { "/me/profile/{collection}": ok(profile({ languages: [] })) });
    await renderScreen(<Section />);
    await press("Add");
    await fireEvent.changeText(await screen.findByLabelText("Language"), "Hindi");
    await press("Native");
    await press("Save");
    await settle();
    expect(body(api.POST)).toEqual({ language: "Hindi", proficiency: "native", can_read: true, can_write: true });
  });

  it("a place needs a state and may leave the district out", async () => {
    world.params = { section: "preferred_locations" };
    withProfile({ preferred_locations: [] });
    serve(api.POST, { "/me/profile/{collection}": ok(profile()) });
    await renderScreen(<Section />);
    await press("Add");
    await press("Save");
    expect(await screen.findByText("This is needed.")).toBeTruthy();
    await fireEvent.changeText(screen.getByLabelText("State"), "Maharashtra");
    await press("Save");
    await settle();
    expect(body(api.POST)).toEqual({ state: "Maharashtra", district: null });
  });
});
