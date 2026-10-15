import { waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";

import TabsLayout from "../../app/(tabs)/_layout";
import { account, api, ok, push, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

const shown: Record<string, Record<string, unknown>> = {};

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("../push", () => require("./mocks").pushModule);
jest.mock("expo-router", () => ({
  ...require("./mocks").routerModule,
  Tabs: Object.assign(({ children }: { children: ReactNode }) => children, {
    Screen: ({ name, options }: { name: string; options: Record<string, unknown> }) => {
      shown[name] = options;
      return null;
    },
  }),
}));

beforeEach(() => {
  resetWorld();
  for (const key of Object.keys(shown)) delete shown[key];
});

describe("the tab bar", () => {
  it("has five places, with Standards out of the bar but still a route", async () => {
    await renderScreen(<TabsLayout />);
    expect(Object.keys(shown)).toEqual(["index", "jobs", "courses", "matches", "me", "skills"]);
    expect(shown.skills.href).toBeNull();
    expect(shown.matches.title).toBe("Matches");
  });

  it("puts a number in the Me label when there are new updates, and says it aloud too", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 4 }) });
    await renderScreen(<TabsLayout />);
    await waitFor(() => expect(shown.me.tabBarLabel).toBe("Me (4)"));
    expect(shown.me.tabBarAccessibilityLabel).toBe("Me, 4 unread");
    // A badge would hang off an icon this bar does not draw: it must not be the way the count shows.
    expect(shown.me.tabBarBadge).toBeUndefined();
  });

  it("shows no number when everything is read", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 0 }) });
    await renderScreen(<TabsLayout />);
    // The count was asked for and answered 0: only then is "no number" a fact about the answer.
    await waitFor(() => expect(api.GET.mock.calls.map((c) => c[0])).toContain("/me/notifications/unread-count"));
    await settle();
    expect(shown.me.tabBarLabel).toBe("Me");
    expect(shown.me.tabBarAccessibilityLabel).toBe("Me");
  });

  it("asks nothing of the server for somebody signed out", async () => {
    await renderScreen(<TabsLayout />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
    expect(shown.me.tabBarLabel).toBe("Me");
  });
});

describe("notifications", () => {
  it("registers this phone only for a signed-in job seeker, and is told who that is", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 0 }) });
    await renderScreen(<TabsLayout />);
    const lastState = () => push.registration.mock.calls[push.registration.mock.calls.length - 1]?.[2];
    await waitFor(() => expect(lastState()).toEqual({ signedIn: true, isJobSeeker: true }));
  });

  it("is told an organisation account is not a job seeker", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account("organisation")) });
    await renderScreen(<TabsLayout />);
    const lastState = () => push.registration.mock.calls[push.registration.mock.calls.length - 1]?.[2];
    await waitFor(() => expect(lastState()).toEqual({ signedIn: true, isJobSeeker: false }));
  });

  it("opens the place a tapped notification names", async () => {
    let go: (path: string) => void = () => undefined;
    push.taps.mockImplementation((fn) => {
      go = fn;
      return () => undefined;
    });
    await renderScreen(<TabsLayout />);
    go("/applications");
    expect(router.push).toHaveBeenCalledWith("/applications");
  });

  it("stops listening when the tabs go away", async () => {
    const stop = jest.fn();
    push.taps.mockReturnValue(stop);
    const view = await renderScreen(<TabsLayout />);
    await view.unmount();
    expect(stop).toHaveBeenCalled();
  });
});
