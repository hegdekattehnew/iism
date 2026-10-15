import { fireEvent, screen } from "@testing-library/react-native";

import { ApplyPanel } from "../ui/ApplyPanel";
import { account, api, application, failed, ok, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const panel = (isOpen = true) => <ApplyPanel jobSlug="ward-assistant-1" organisation="Apollo Care" isOpen={isOpen} />;

/** A signed-in job seeker whose applications and saved vacancies are as given. */
function signedIn(applications: unknown[] = [], saved: unknown[] = [], kind: "seeker" | "organisation" = "seeker") {
  world.signedIn = true;
  serve(api.GET, {
    "/auth/me": ok(account(kind)),
    "/me/applications": ok(applications),
    "/me/saved-jobs": ok(saved),
  });
}

const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));
const posted = (path: string) => api.POST.mock.calls.filter((c) => c[0] === path);

describe("signed out", () => {
  it("offers a way in and makes no request that could only answer 401", async () => {
    await renderScreen(panel());
    await press("Sign in to apply");
    expect(router.push).toHaveBeenCalledWith("/sign-in");
    expect(api.GET).not.toHaveBeenCalled();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("says a closed vacancy is closed before asking anybody to sign in", async () => {
    await renderScreen(panel(false));
    expect(await screen.findByText(/This vacancy is closed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign in to apply" })).toBeNull();
  });
});

describe("an account that is not a job seeker", () => {
  it("is offered nothing, and no request is made for what it cannot do", async () => {
    signedIn([], [], "organisation");
    await renderScreen(panel());
    await settle();
    expect(screen.queryByRole("button", { name: "Apply for this job" })).toBeNull();
    expect(api.GET.mock.calls.map((c) => c[0])).toEqual(["/auth/me"]);
  });

  it("is offered nothing while it is still not known which it is", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": new Promise(() => undefined) });
    await renderScreen(panel());
    await settle();
    expect(screen.queryByRole("button", { name: "Apply for this job" })).toBeNull();
  });
});

describe("applying", () => {
  it("asks first, and the question names the organisation and what is shared", async () => {
    signedIn();
    await renderScreen(panel());
    await press("Apply for this job");
    expect(await screen.findByText("Before you apply")).toBeTruthy();
    expect(
      screen.getByText(/Applying sends your name, mobile number and email to Apollo Care, for this vacancy only/),
    ).toBeTruthy();
    expect(screen.getByText(/If you withdraw later, they stop seeing your contact details/)).toBeTruthy();
    // Nothing has been sent: the disclosure is made by the button that says so, not by this one.
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("sends the vacancy and the note only when the person confirms", async () => {
    signedIn();
    serve(api.POST, { "/me/applications": ok(application(1)) });
    await renderScreen(panel());
    await press("Apply for this job");
    await fireEvent.changeText(await screen.findByLabelText("Add a note (optional)"), "Two years on a ward.");
    await press("Yes, apply");
    await settle();
    expect(posted("/me/applications")).toHaveLength(1);
    expect(posted("/me/applications")[0][1]).toEqual({ body: { job_slug: "ward-assistant-1", message: "Two years on a ward." } });
  });

  it("sends nothing at all when the person cancels", async () => {
    signedIn();
    await renderScreen(panel());
    await press("Apply for this job");
    await press("Cancel");
    expect(api.POST).not.toHaveBeenCalled();
    expect(screen.queryByText("Before you apply")).toBeNull();
    expect(await screen.findByRole("button", { name: "Apply for this job" })).toBeTruthy();
  });

  it("shows applied, with a way to withdraw, once the application exists", async () => {
    signedIn([application(1)]);
    await renderScreen(panel());
    expect(await screen.findByText("Applied")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply for this job" })).toBeNull();
  });

  it.each([
    [409, /You have already applied for this job/],
    [429, /You have applied to a lot of jobs today/],
    [403, /set up for an organisation/],
    [500, /Something went wrong/],
  ])("says what a %s means, not a generic line", async (status, words) => {
    signedIn();
    serve(api.POST, { "/me/applications": failed(status) });
    await renderScreen(panel());
    await press("Apply for this job");
    await press("Yes, apply");
    expect(await screen.findByText(words)).toBeTruthy();
    expect(screen.queryByText(/session has expired/)).toBeNull();
  });

  it("says the session ended on a 401 rather than that the application failed", async () => {
    signedIn();
    serve(api.POST, { "/me/applications": failed(401) });
    await renderScreen(panel());
    await press("Apply for this job");
    await press("Yes, apply");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    expect(screen.queryByText(/Something went wrong/)).toBeNull();
  });

  it("keeps the note and the question open after a failure so nothing typed is lost", async () => {
    signedIn();
    serve(api.POST, { "/me/applications": failed(500) });
    await renderScreen(panel());
    await press("Apply for this job");
    await fireEvent.changeText(await screen.findByLabelText("Add a note (optional)"), "kept");
    await press("Yes, apply");
    await screen.findByText(/Something went wrong/);
    expect(screen.getByDisplayValue("kept")).toBeTruthy();
  });
});

describe("withdrawing", () => {
  it.each(["applied", "shortlisted"])("is offered to an application that is %s", async (status) => {
    signedIn([application(1, { status })]);
    await renderScreen(panel());
    expect(await screen.findByRole("button", { name: "Withdraw" })).toBeTruthy();
  });

  it.each(["rejected", "hired", "completed", "no_show"])("is not offered once the employer has decided: %s", async (status) => {
    signedIn([application(1, { status })]);
    await renderScreen(panel());
    expect(await screen.findByText(status === "rejected" ? "Not selected" : /Hired|Completed|Did not attend/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("calls the withdraw route for that application", async () => {
    signedIn([application(1)]);
    serve(api.POST, { "/me/applications/{application_id}/withdraw": ok(application(1, { status: "withdrawn" })) });
    await renderScreen(panel());
    await press("Withdraw");
    await settle();
    const call = posted("/me/applications/{application_id}/withdraw")[0];
    expect(call[1]).toEqual({ params: { path: { application_id: "a1" } } });
  });

  it("says a decision was made when the server refuses with a 409", async () => {
    signedIn([application(1)]);
    serve(api.POST, { "/me/applications/{application_id}/withdraw": failed(409) });
    await renderScreen(panel());
    await press("Withdraw");
    expect(await screen.findByText(/A decision has been made on this application/)).toBeTruthy();
  });

  it("offers to apply again after a withdrawal, since the application is over", async () => {
    signedIn([application(1, { status: "withdrawn" })]);
    await renderScreen(panel());
    expect(await screen.findByRole("button", { name: "Apply for this job" })).toBeTruthy();
  });
});

describe("saving for later", () => {
  it("saves, and says so, with the vacancy's own slug", async () => {
    signedIn();
    serve(api.POST, { "/me/saved-jobs": ok({ job: {}, saved_at: "x" }) });
    await renderScreen(panel());
    await press("Save for later");
    await settle();
    expect(posted("/me/saved-jobs")[0][1]).toEqual({ body: { job_slug: "ward-assistant-1" } });
  });

  it("unsaves what is saved", async () => {
    signedIn([], [{ job: { slug: "ward-assistant-1" }, saved_at: "x" }]);
    serve(api.DELETE, { "/me/saved-jobs/{job_slug}": ok(undefined) });
    await renderScreen(panel());
    await press("Saved");
    await settle();
    expect(api.DELETE.mock.calls[0]).toEqual(["/me/saved-jobs/{job_slug}", { params: { path: { job_slug: "ward-assistant-1" } } }]);
  });

  it("says when it could not", async () => {
    signedIn();
    serve(api.POST, { "/me/saved-jobs": failed(500) });
    await renderScreen(panel());
    await press("Save for later");
    expect(await screen.findByText(/Something went wrong/)).toBeTruthy();
  });
});
