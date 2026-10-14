import { fireEvent, screen } from "@testing-library/react-native";

import Search from "../../app/search";
import { api, failed, job, ok, page, resetWorld, router, skill, world } from "./mocks";
import { renderScreen } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const role = { slug: "gda", job_role: "General Duty Assistant", qp_code: "HSS/Q5101", sector_name: "Healthcare", standards_count: 7, variants: 1, matched_on: "General Duty Assistant", match_kind: "exact" };

function answer(jobs = page([job(1)], 12), roles = [role], standards = [skill(1)]) {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/jobs") return ok(jobs);
    if (path === "/roles/search") return ok(roles);
    return ok(standards);
  });
}

describe("the search screen", () => {
  it("asks nothing until there is a term, and says what to type", async () => {
    await renderScreen(<Search />);
    expect(screen.getByText("Type a job title or a skill above.")).toBeTruthy();
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("answers jobs first, then roles, then standards, in that order on the screen", async () => {
    world.params = { q: "nurse" };
    answer();
    await renderScreen(<Search />);
    await screen.findByText("Ward assistant 1");
    const text = JSON.stringify(screen.toJSON());
    const at = (needle: string) => text.indexOf(needle);
    expect(at("Open jobs")).toBeGreaterThan(-1);
    expect(at("Open jobs")).toBeLessThan(at("Job roles"));
    expect(at("Job roles")).toBeLessThan(at("Skill standards"));
    expect(screen.getByText("General Duty Assistant")).toBeTruthy();
    expect(screen.getByText("Healthcare · 7 standards")).toBeTruthy();
    expect(screen.getByText("Hand hygiene 1")).toBeTruthy();
  });

  it("offers every match when there are more than the preview, carrying the term across", async () => {
    world.params = { q: "nurse" };
    answer();
    await renderScreen(<Search />);
    await fireEvent.press(await screen.findByRole("button", { name: "See all 12 jobs" }));
    expect(router.navigate).toHaveBeenCalledWith({ pathname: "/jobs", params: { q: "nurse" } });
  });

  it("says each band that has nothing, separately", async () => {
    world.params = { q: "zzz" };
    answer(page([]), [], []);
    await renderScreen(<Search />);
    expect(await screen.findByText("No open vacancy matches this yet.")).toBeTruthy();
    expect(screen.getByText("No job role by that name.")).toBeTruthy();
    expect(screen.getByText("No standard matches this.")).toBeTruthy();
  });

  it("lets one band fail without hiding the others", async () => {
    world.params = { q: "nurse" };
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/roles/search") return failed(500);
      return path === "/jobs" ? ok(page([job(1)])) : ok([skill(1)]);
    });
    await renderScreen(<Search />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(await screen.findByText("This page could not load")).toBeTruthy();
    expect(screen.getByText("Hand hygiene 1")).toBeTruthy();
  });

  it("searches again with what is typed", async () => {
    world.params = { q: "nurse" };
    answer();
    await renderScreen(<Search />);
    await screen.findByText("Ward assistant 1");
    await fireEvent.changeText(screen.getByLabelText("e.g. General Duty Assistant, welding, retail sales"), "welder");
    await fireEvent.press(screen.getByRole("button", { name: "Search" }));
    expect(router.setParams).toHaveBeenCalledWith({ q: "welder" });
  });
});
