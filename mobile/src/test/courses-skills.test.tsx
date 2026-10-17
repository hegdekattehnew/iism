import { fireEvent, screen, waitFor } from "@testing-library/react-native";

import Courses from "../../app/(tabs)/courses";
import Skills from "../../app/(tabs)/skills";
import { api, course, failed, ok, page, resetWorld, router, skill } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());
const asked = () => api.GET.mock.calls.map((c) => ({ path: c[0], query: c[1]?.params?.query }));

describe("the courses list", () => {
  it("shows a placeholder first, never 'no courses' before the answer", async () => {
    api.GET.mockReturnValue(new Promise(() => undefined));
    await renderScreen(<Courses />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText(/No courses/)).toBeNull();
  });

  it("shows where, when, what it costs and how long, in the shared words", async () => {
    api.GET.mockResolvedValue(ok(page([course(1)])));
    await renderScreen(<Courses />);
    expect(await screen.findByText("Phlebotomy 1")).toBeTruthy();
    expect(screen.getByText("Pune Skills Academy")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra · Starts 2 Nov 2026")).toBeTruthy();
    expect(screen.getByText("₹12,500 · 120 hours")).toBeTruthy();
    expect(screen.getByText("1 course")).toBeTruthy();
  });

  it("says a course that has started has started, and a free one is free", async () => {
    api.GET.mockResolvedValue(
      ok(page([course(1, { started: true, starts_on: "2026-09-02", fee_inr: 0, duration_hours: null })])),
    );
    await renderScreen(<Courses />);
    expect(await screen.findByText("Pune, Maharashtra · Started 2 Sep 2026")).toBeTruthy();
    expect(screen.getByText("Free")).toBeTruthy();
  });

  it("says what the qualification is worth, and draws nothing for a zero or a missing figure (Sprint 75)", async () => {
    api.GET.mockResolvedValue(
      ok(
        page([
          course(1, { qualification_credits: 14 }),
          course(2, { qualification_credits: 0 }),
          course(3, { qualification_credits: null }),
        ]),
      ),
    );
    await renderScreen(<Courses />);
    expect(await screen.findByText("14 credits")).toBeTruthy();
    expect(screen.queryAllByText(/credit/)).toHaveLength(1);
  });

  it("gives an online course no place at all", async () => {
    api.GET.mockResolvedValue(ok(page([course(1, { mode: "online", starts_on: null })])));
    await renderScreen(<Courses />);
    await screen.findByText("Phlebotomy 1");
    expect(screen.queryByText(/Maharashtra/)).toBeNull();
    expect(screen.queryByText(/Where/)).toBeNull();
  });

  it("filters by mode and by what is typed", async () => {
    api.GET.mockResolvedValue(ok(page([course(1)])));
    await renderScreen(<Courses />);
    await screen.findByText("Phlebotomy 1");
    await fireEvent.press(screen.getByRole("button", { name: "In person" }));
    await waitFor(() => expect(asked().some((a) => a.query?.mode === "offline")).toBe(true));
    await fireEvent.changeText(screen.getByLabelText("Search courses — English or Hindi"), "weld");
    await waitFor(() => expect(asked().some((a) => a.query?.q === "weld")).toBe(true));
    await settle();
  });

  it("says it could not load, then recovers", async () => {
    api.GET.mockResolvedValue(failed(500));
    await renderScreen(<Courses />);
    expect(await screen.findByText("This page could not load")).toBeTruthy();
    api.GET.mockResolvedValue(ok(page([course(2)])));
    await fireEvent.press(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Phlebotomy 2")).toBeTruthy();
  });

  it("opens a course", async () => {
    api.GET.mockResolvedValue(ok(page([course(3)])));
    await renderScreen(<Courses />);
    await fireEvent.press(await screen.findByRole("button", { name: "Phlebotomy 3" }));
    expect(router.push).toHaveBeenCalledWith("/course/phlebotomy-3");
  });
});

describe("the standards list", () => {
  it("shows the code and the qualification it comes from", async () => {
    api.GET.mockResolvedValue(ok(page([skill(1)])));
    await renderScreen(<Skills />);
    expect(await screen.findByText("Hand hygiene 1")).toBeTruthy();
    expect(screen.getByText("HSS/N1")).toBeTruthy();
    expect(screen.getByText("General Duty Assistant · Healthcare")).toBeTruthy();
  });

  it("flags two standards with one name, so the codes can be compared", async () => {
    api.GET.mockResolvedValue(
      ok(page([skill(1, { name: "Hand hygiene" }), skill(2, { name: "Hand hygiene", nos_code: "HSS/N2" }), skill(3)])),
    );
    await renderScreen(<Skills />);
    await screen.findAllByText("Hand hygiene");
    expect(screen.getAllByText("Same name as another result — compare the codes")).toHaveLength(2);
  });

  it("browses the catalogue by type, and searches by a different route that is not paged", async () => {
    api.GET.mockImplementation(async (path: string) =>
      path === "/skills/search" ? ok([skill(9)]) : ok(page([skill(1)])),
    );
    await renderScreen(<Skills />);
    await screen.findByText("Hand hygiene 1");

    await fireEvent.press(screen.getByRole("button", { name: "Core" }));
    await waitFor(() => expect(asked().some((a) => a.path === "/skills" && a.query?.skill_type === "core")).toBe(true));

    await fireEvent.changeText(screen.getByLabelText("Try 'blood', 'रक्त' or 'khoon nikalna'"), "blood");
    expect(await screen.findByText("Hand hygiene 9")).toBeTruthy();
    expect(asked().some((a) => a.path === "/skills/search" && a.query?.q === "blood")).toBe(true);
    // The server ranks a search across every type, so the type chips go away.
    expect(screen.queryByRole("button", { name: "Core" })).toBeNull();
  });

  it("opens a standard", async () => {
    api.GET.mockResolvedValue(ok(page([skill(4)])));
    await renderScreen(<Skills />);
    await fireEvent.press(await screen.findByRole("button", { name: "Hand hygiene 4" }));
    expect(router.push).toHaveBeenCalledWith("/skill/hand-hygiene-4");
  });
});
