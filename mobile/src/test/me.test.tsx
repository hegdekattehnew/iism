import { fireEvent, screen } from "@testing-library/react-native";

import Me from "../../app/(tabs)/me";
import { account, api, ok, profile, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);
jest.mock("../core/sign-in", () => ({ ...jest.requireActual("../core/sign-in"), signOut: jest.fn(async () => undefined) }));

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

  it("shows the person, how complete the profile is, and the four places to go", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/profile": ok(profile()) });
    await renderScreen(<Me />);
    expect(await screen.findByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("Ward boy")).toBeTruthy();
    expect(screen.getByText("Profile 60% complete")).toBeTruthy();
    for (const [name, path] of [
      ["My profile", "/profile"],
      ["My applications", "/applications"],
      ["Saved jobs", "/saved"],
      ["Courses I asked about", "/interests"],
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
});
