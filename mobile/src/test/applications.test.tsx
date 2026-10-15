import { fireEvent, screen } from "@testing-library/react-native";

import Applications from "../../app/applications";
import Interests from "../../app/interests";
import Saved from "../../app/saved";
import { account, api, application, failed, interest, ok, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

describe("my applications", () => {
  const listed = (items: unknown[]) => serve(api.GET, { "/auth/me": ok(account()), "/me/applications": ok(items) });

  it("offers 'why not me' on a rejection, and only on a rejection", async () => {
    listed([application(1, { status: "rejected" }), application(2), application(3, { status: "shortlisted" }), application(4, { status: "withdrawn" })]);
    await renderScreen(<Applications />);
    await screen.findByText("Ward assistant 1");
    expect(screen.getAllByRole("button", { name: "See what you were missing" })).toHaveLength(1);
    await fireEvent.press(screen.getByRole("button", { name: "See what you were missing" }));
    expect(router.push).toHaveBeenCalledWith("/gap/a1");
  });

  it("makes no request when signed out", async () => {
    world.signedIn = false;
    await renderScreen(<Applications />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
  });

  it("shows each application with where it stands and the day it was made, in India", async () => {
    listed([application(1), application(2, { status: "shortlisted" })]);
    await renderScreen(<Applications />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.getByText("Applied")).toBeTruthy();
    expect(screen.getByText("Shortlisted")).toBeTruthy();
    expect(screen.getByText(/The employer has your application/)).toBeTruthy();
    // 20:00 UTC on the 14th is already the 15th in India.
    expect(screen.getAllByText("Applied on 15 Oct 2026").length).toBe(2);
  });

  it("shows what the employer said, from the application itself, and says who said it", async () => {
    listed([application(1, { status: "shortlisted", status_message: "Interview on Monday at 10, Pune office." })]);
    await renderScreen(<Applications />);
    expect(await screen.findByText("Interview on Monday at 10, Pune office.")).toBeTruthy();
    expect(screen.getByText("A message from Apollo Care")).toBeTruthy();
  });

  it("shows nothing of the employer's once the application is withdrawn", async () => {
    listed([application(1, { status: "withdrawn", status_message: "Interview on Monday." })]);
    await renderScreen(<Applications />);
    await screen.findByText("Withdrawn");
    expect(screen.queryByText("Interview on Monday.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("offers withdrawing only where the employer has not decided", async () => {
    listed([application(1), application(2, { status: "rejected" }), application(3, { status: "hired" })]);
    await renderScreen(<Applications />);
    await screen.findByText("Ward assistant 1");
    expect(screen.getAllByRole("button", { name: "Withdraw" })).toHaveLength(1);
    expect(screen.getByText("Not selected")).toBeTruthy();
  });

  it("withdraws that application, and says a decision was made if the server refuses", async () => {
    listed([application(1)]);
    serve(api.POST, { "/me/applications/{application_id}/withdraw": failed(409) });
    await renderScreen(<Applications />);
    await fireEvent.press(await screen.findByRole("button", { name: "Withdraw" }));
    expect(await screen.findByText(/A decision has been made on this application/)).toBeTruthy();
    expect(api.POST.mock.calls[0][1]).toEqual({ params: { path: { application_id: "a1" } } });
  });

  it("does not nest a button inside a button: the card is not one, its own button opens the job", async () => {
    // A pressable card that holds a Withdraw button is invalid on the web and hides the inner button
    // from a screen reader (found by running the screen in a browser).
    listed([application(1)]);
    await renderScreen(<Applications />);
    await screen.findByText("Ward assistant 1");
    expect(screen.queryByRole("button", { name: "Ward assistant 1" })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "View the job" }));
    expect(router.push).toHaveBeenCalledWith("/job/ward-assistant-1");
  });

  it("says a vacancy removed by the team was removed", async () => {
    listed([application(1, { job: { ...application(1).job, removed: true } })]);
    await renderScreen(<Applications />);
    expect(await screen.findByText("Removed by our team")).toBeTruthy();
  });

  it("points at the matches when there is nothing yet", async () => {
    listed([]);
    await renderScreen(<Applications />);
    expect(await screen.findByText("You have not applied for anything yet.")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "See your matches" }));
    expect(router.navigate).toHaveBeenCalledWith("/matches");
  });

  it("says the session ended on a 401, not that the list could not load", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/applications": failed(401) });
    await renderScreen(<Applications />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});

describe("saved vacancies", () => {
  it("lists them and lets one go", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/saved-jobs": ok([{ job: application(1).job, saved_at: "2026-10-14T20:00:00+00:00" }]),
    });
    serve(api.DELETE, { "/me/saved-jobs/{job_slug}": ok(undefined) });
    await renderScreen(<Saved />);
    expect(await screen.findByText("Ward assistant 1")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ward assistant 1" })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "View the job" }));
    expect(router.push).toHaveBeenCalledWith("/job/ward-assistant-1");
    await fireEvent.press(screen.getByRole("button", { name: "Saved" }));
    await settle();
    expect(api.DELETE.mock.calls[0][1]).toEqual({ params: { path: { job_slug: "ward-assistant-1" } } });
  });

  it("says when there are none", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/saved-jobs": ok([]) });
    await renderScreen(<Saved />);
    expect(await screen.findByText("You have not saved any jobs yet.")).toBeTruthy();
  });
});

describe("the courses I asked about", () => {
  it("shows where each stands and lets one be withdrawn", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/course-interests": ok([interest(1), interest(2, { status: "enrolled" })]) });
    serve(api.POST, { "/me/course-interests/{interest_id}/withdraw": ok(interest(1, { status: "withdrawn" })) });
    await renderScreen(<Interests />);
    expect(await screen.findByText("Phlebotomy 1")).toBeTruthy();
    expect(screen.getByText("Registered")).toBeTruthy();
    expect(screen.getByText("Enrolled")).toBeTruthy();
    expect(screen.getAllByText("Registered on 15 Oct 2026")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Phlebotomy 1" })).toBeNull();
    await fireEvent.press(screen.getAllByRole("button", { name: "View the course" })[0]);
    expect(router.push).toHaveBeenCalledWith("/course/phlebotomy-1");
    await fireEvent.press(screen.getAllByRole("button", { name: "Withdraw" })[0]);
    await settle();
    expect(api.POST.mock.calls[0][1]).toEqual({ params: { path: { interest_id: "i1" } } });
  });

  it("offers nothing to withdraw once it is withdrawn", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/course-interests": ok([interest(1, { status: "withdrawn" })]) });
    await renderScreen(<Interests />);
    await screen.findByText("Withdrawn");
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("points at the courses when there are none", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/course-interests": ok([]) });
    await renderScreen(<Interests />);
    await fireEvent.press(await screen.findByRole("button", { name: "Browse courses" }));
    expect(router.navigate).toHaveBeenCalledWith("/courses");
  });
});
