import { fireEvent, screen } from "@testing-library/react-native";

import Me from "../../app/(tabs)/me";
import { account, api, endSession, ok, profile, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

describe("my page", () => {
  it("asks a signed-out person to sign in, makes no request and offers no sign-out", async () => {
    await renderScreen(<Me />);
    await settle();
    expect(screen.getByText("Sign in to see your matches, applications and profile.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
    expect(api.GET).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByRole("button", { name: "Sign in" }));
    expect(router.push).toHaveBeenCalledWith("/sign-in");
  });

  it("shows the person, how complete the profile is, and the places to go", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/profile": ok(profile()) });
    await renderScreen(<Me />);
    expect(await screen.findByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("Ward boy")).toBeTruthy();
    expect(screen.getByText("Profile 60% complete")).toBeTruthy();
    for (const [name, path] of [
      ["My profile", "/profile"],
      ["Updates", "/notices"],
      ["My applications", "/applications"],
      ["Saved jobs", "/saved"],
      ["Courses I asked about", "/interests"],
      ["Your account", "/account"],
      ["Contact us", "/contact"],
    ] as const) {
      await fireEvent.press(screen.getByRole("button", { name }));
      expect(router.push).toHaveBeenCalledWith(path);
    }
  });

  it("lets an organisation owner who signed in on a phone sign out, and says where to go instead", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account("organisation")) });
    await renderScreen(<Me />);
    expect(await screen.findByText(/This app is for job seekers/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
    expect(api.GET.mock.calls.map((c) => c[0])).toEqual(["/auth/me"]);
  });

  it("shows how many updates are new, in the label and for a screen reader", async () => {
    world.signedIn = true;
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/profile": ok(profile()),
      "/me/notifications/unread-count": ok({ unread: 3 }),
    });
    await renderScreen(<Me />);
    expect(await screen.findByRole("button", { name: "Updates: 3 new updates" })).toBeTruthy();
    expect(screen.getByText("Updates (3)")).toBeTruthy();
  });

  it("says nothing of a count when there are no new updates", async () => {
    world.signedIn = true;
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/profile": ok(profile()),
      "/me/notifications/unread-count": ok({ unread: 0 }),
    });
    await renderScreen(<Me />);
    expect(await screen.findByRole("button", { name: "Updates" })).toBeTruthy();
  });

  it("signs out through the one function that takes the phone off the push list first", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account("organisation")) });
    await renderScreen(<Me />);
    await fireEvent.press(await screen.findByRole("button", { name: "Sign out" }));
    expect(endSession).toHaveBeenCalledTimes(1);
  });
});
