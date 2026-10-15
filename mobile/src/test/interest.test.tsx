import { fireEvent, screen } from "@testing-library/react-native";

import { InterestPanel } from "../ui/InterestPanel";
import { account, api, failed, interest, ok, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const panel = () => <InterestPanel courseSlug="phlebotomy-1" organisation="Pune Skills Academy" />;
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));

function signedIn(interests: unknown[] = [], kind: "seeker" | "organisation" = "seeker") {
  world.signedIn = true;
  serve(api.GET, { "/auth/me": ok(account(kind)), "/me/course-interests": ok(interests) });
}

describe("registering interest in a course", () => {
  it("asks a signed-out person to sign in and makes no request", async () => {
    await renderScreen(panel());
    await press("Sign in to register interest");
    expect(router.push).toHaveBeenCalledWith("/sign-in");
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("offers nothing to an organisation account", async () => {
    signedIn([], "organisation");
    await renderScreen(panel());
    await settle();
    expect(screen.queryByRole("button", { name: "I'm interested in this course" })).toBeNull();
  });

  it("names the provider and what they will see before anything is sent", async () => {
    signedIn();
    await renderScreen(panel());
    await press("I'm interested in this course");
    expect(
      await screen.findByText(/Pune Skills Academy will see your name, phone number, email and district/),
    ).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("sends the course and the note on confirming, and nothing on cancelling", async () => {
    signedIn();
    serve(api.POST, { "/me/course-interests": ok(interest(1)) });
    await renderScreen(panel());
    await press("I'm interested in this course");
    await press("Cancel");
    expect(api.POST).not.toHaveBeenCalled();
    await press("I'm interested in this course");
    await fireEvent.changeText(await screen.findByLabelText("Anything they should know (optional)"), "evenings only");
    await press("Register my interest");
    await settle();
    expect(api.POST.mock.calls[0]).toEqual(["/me/course-interests", { body: { course_slug: "phlebotomy-1", message: "evenings only" } }]);
  });

  it("shows it as registered with a way to withdraw", async () => {
    signedIn([interest(1)]);
    await renderScreen(panel());
    expect(await screen.findByText("Interest registered")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw" })).toBeTruthy();
  });

  it.each([
    [409, /You have already registered interest in this course/],
    [429, /registered interest in a lot of courses today/],
    [403, /Only a job seeker account can register interest/],
    [500, /That did not work/],
  ])("says what a %s means", async (status, words) => {
    signedIn();
    serve(api.POST, { "/me/course-interests": failed(status) });
    await renderScreen(panel());
    await press("I'm interested in this course");
    await press("Register my interest");
    expect(await screen.findByText(words)).toBeTruthy();
  });

  it("says the session ended on a 401", async () => {
    signedIn();
    serve(api.POST, { "/me/course-interests": failed(401) });
    await renderScreen(panel());
    await press("I'm interested in this course");
    await press("Register my interest");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});
