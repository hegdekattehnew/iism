import { fireEvent, screen } from "@testing-library/react-native";

import { ReportPanel } from "../ui/ReportPanel";
import { api, failed, ok, resetWorld, serve, world } from "./mocks";
import { renderScreen } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));

describe("reporting a vacancy or a course", () => {
  it("says to sign in, offers no form that cannot succeed, and adds no sign-in button of its own", async () => {
    await renderScreen(<ReportPanel target="job" slug="ward-assistant-1" />);
    expect(screen.getByText(/Sign in to report a listing/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Report this vacancy" })).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("names the right thing on a vacancy and on a course", async () => {
    world.signedIn = true;
    await renderScreen(<ReportPanel target="job" slug="x" />);
    expect(await screen.findByRole("button", { name: "Report this vacancy" })).toBeTruthy();
    await renderScreen(<ReportPanel target="course" slug="x" />);
    expect(await screen.findByRole("button", { name: "Report this course" })).toBeTruthy();
  });

  it("sends a vacancy report to its route with the reason and the detail, and says only that it was received", async () => {
    world.signedIn = true;
    serve(api.POST, { "/jobs/{slug}/report": ok({ received: true }) });
    await renderScreen(<ReportPanel target="job" slug="ward-assistant-1" />);
    await press("Report this vacancy");
    await press("Asks for money");
    await fireEvent.changeText(screen.getByLabelText("Anything else we should know?"), " wanted a fee ");
    await press("Send report");
    expect(await screen.findByText(/Thank you. We have your report/)).toBeTruthy();
    expect(api.POST.mock.calls[0]).toEqual([
      "/jobs/{slug}/report",
      { params: { path: { slug: "ward-assistant-1" } }, body: { reason: "asks_for_money", detail: "wanted a fee" } },
    ]);
  });

  it("sends a course report to the course route", async () => {
    world.signedIn = true;
    serve(api.POST, { "/courses/{slug}/report": ok({ received: true }) });
    await renderScreen(<ReportPanel target="course" slug="phlebotomy-1" />);
    await press("Report this course");
    await press("Send report");
    await screen.findByText(/Thank you/);
    expect(api.POST.mock.calls[0][0]).toBe("/courses/{slug}/report");
  });

  it.each([
    [409, "You have already reported this listing.", /You have already reported this listing\./],
    [403, "You manage this listing.", /You manage this listing\./],
    [429, undefined, /sent several reports today/],
    [500, undefined, /Could not send your report/],
  ])("says what a %s means", async (status, detail, words) => {
    world.signedIn = true;
    serve(api.POST, { "/jobs/{slug}/report": failed(status, detail) });
    await renderScreen(<ReportPanel target="job" slug="x" />);
    await press("Report this vacancy");
    await press("Send report");
    expect(await screen.findByText(words)).toBeTruthy();
  });

  it("says the session ended on a 401", async () => {
    world.signedIn = true;
    serve(api.POST, { "/jobs/{slug}/report": failed(401) });
    await renderScreen(<ReportPanel target="job" slug="x" />);
    await press("Report this vacancy");
    await press("Send report");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});
