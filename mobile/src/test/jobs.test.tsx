import { act, fireEvent, screen, waitFor } from "@testing-library/react-native";

import Jobs from "../../app/(tabs)/jobs";
import hi from "../messages/hi.json";
import { api, failed, job, ok, page, resetWorld, router, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const asked = () => api.GET.mock.calls.map((c) => ({ path: c[0], query: c[1]?.params?.query }));

describe("the vacancies list", () => {
  it("shows a placeholder until the first answer, and never 'no jobs' before it", async () => {
    let answer!: (value: unknown) => void;
    api.GET.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    await renderScreen(<Jobs />);

    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText(/No jobs/)).toBeNull();
    expect(screen.queryByText("No jobs match.")).toBeNull();

    await act(async () => answer(ok(page([job(1)]))));
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.queryByLabelText("Loading")).toBeNull();
  });

  it("shows each vacancy with its employer, place, terms and the total", async () => {
    api.GET.mockResolvedValue(ok(page([job(1), job(2)])));
    await renderScreen(<Jobs />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.getAllByText("Apollo Care")).toHaveLength(2);
    expect(screen.getAllByText("Pune, Maharashtra")).toHaveLength(2);
    // Indian grouping, from the shared words: not 240,000.
    expect(screen.getAllByText(/₹2,40,000–3,60,000 per year/)).toHaveLength(2);
    expect(screen.getByText("2 jobs")).toBeTruthy();
  });

  it("asks for twenty at a time", async () => {
    api.GET.mockResolvedValue(ok(page([job(1)])));
    await renderScreen(<Jobs />);
    await screen.findByText("Ward assistant 1");
    expect(asked()[0].path).toBe("/jobs");
    expect(asked()[0].query).toMatchObject({ limit: 20, offset: 0 });
  });

  it("sends what is typed, and an employment type when a chip is chosen", async () => {
    api.GET.mockResolvedValue(ok(page([job(1)])));
    await renderScreen(<Jobs />);
    await screen.findByText("Ward assistant 1");

    await fireEvent.changeText(screen.getByLabelText("Search job titles — English or Hindi"), "nurse");
    await waitFor(() => expect(asked().some((a) => a.query?.q === "nurse")).toBe(true));

    await fireEvent.press(screen.getByRole("button", { name: "Gig (short-term)" }));
    await waitFor(() => expect(asked().some((a) => a.query?.employment_type === "gig")).toBe(true));
    expect(screen.getByRole("button", { name: "Gig (short-term)" })).toBeSelected();
    await settle();
  });

  it("says there are none, once it knows", async () => {
    api.GET.mockResolvedValue(ok(page([])));
    await renderScreen(<Jobs />);
    expect(await screen.findByText(/No jobs match/)).toBeTruthy();
  });

  it("says what went wrong when the first page fails, and retries", async () => {
    api.GET.mockResolvedValue(failed(503, "Database unavailable"));
    await renderScreen(<Jobs />);
    expect(await screen.findByText("This page could not load")).toBeTruthy();
    expect(screen.queryByText(/No jobs match/)).toBeNull();

    api.GET.mockResolvedValue(ok(page([job(1)])));
    await fireEvent.press(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
  });

  it("loads the next page at the end of the list and keeps what is on screen when that fails", async () => {
    const first = Array.from({ length: 20 }, (_, i) => job(i + 1));
    api.GET.mockResolvedValueOnce(ok({ ...page(first, 45) }));
    await renderScreen(<Jobs />);
    await screen.findByText("Ward assistant 1");

    api.GET.mockResolvedValueOnce(failed(500));
    await fireEvent(screen.getByTestId("result-list"), "endReached");
    expect(await screen.findByText(/Could not load more/)).toBeTruthy();
    expect(screen.getByText("Ward assistant 1")).toBeTruthy();
    expect(asked()[1].query).toMatchObject({ offset: 20 });
  });

  it("opens a vacancy", async () => {
    api.GET.mockResolvedValue(ok(page([job(7)])));
    await renderScreen(<Jobs />);
    await fireEvent.press(await screen.findByRole("button", { name: "Ward assistant 7" }));
    expect(router.push).toHaveBeenCalledWith("/job/ward-assistant-7");
  });

  it("starts from the term the search screen handed over", async () => {
    world.params = { q: "welder" };
    api.GET.mockResolvedValue(ok(page([job(1)])));
    await renderScreen(<Jobs />);
    await screen.findByText("Ward assistant 1");
    expect(asked()[0].query).toMatchObject({ q: "welder" });
  });

  it("speaks Hindi from the web's catalogue", async () => {
    world.locale = "hi";
    api.GET.mockResolvedValue(ok(page([job(1)])));
    await renderScreen(<Jobs />, "hi");
    await screen.findByText("Ward assistant 1");
    expect(screen.getByLabelText(hi.jobsPage.searchPlaceholder)).toBeTruthy();
    expect(screen.queryByLabelText("Search job titles — English or Hindi")).toBeNull();
  });
});
