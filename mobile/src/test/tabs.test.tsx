import { waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";

import TabsLayout from "../../app/(tabs)/_layout";
import { account, api, ok, push, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

const shown: Record<string, Record<string, unknown>> = {};

jest.mock("../runtime", () => require("./mocks").runtimeModule);
// The harness renders no `SafeAreaProvider`; the layout reads the bottom inset to size the bar.
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 0, left: 0, right: 0, bottom: 20 }),
}));
jest.mock("../push", () => require("./mocks").pushModule);
jest.mock("expo-router", () => ({
  ...require("./mocks").routerModule,
  Tabs: Object.assign(
    ({ children, screenOptions }: { children: ReactNode; screenOptions?: Record<string, unknown> }) => {
      shown.__bar = screenOptions ?? {};
      return children;
    },
    {
      Screen: ({ name, options }: { name: string; options: Record<string, unknown> }) => {
        shown[name] = options;
        return null;
      },
    },
  ),
}));

beforeEach(() => {
  resetWorld();
  for (const key of Object.keys(shown)) delete shown[key];
});

describe("the tab bar", () => {
  it("has five places, with Standards out of the bar but still a route", async () => {
    await renderScreen(<TabsLayout />);
    expect(Object.keys(shown).filter((k) => k !== "__bar")).toEqual(["index", "jobs", "courses", "matches", "me", "skills"]);
    expect(shown.skills.href).toBeNull();
    expect(shown.matches.title).toBe("Matches");
  });

  it("is tall enough for an icon over a label, and clears the bottom inset", async () => {
    await renderScreen(<TabsLayout />);
    const style = (shown.__bar as { tabBarStyle: { height: number; paddingBottom: number } }).tabBarStyle;
    expect(style.height).toBe(64 + 20); // the 20 dp the mocked inset reports
    expect(style.height - style.paddingBottom).toBeGreaterThanOrEqual(48); // what is left for the touch target
    expect(style.paddingBottom).toBeGreaterThanOrEqual(20);
  });

  it("gives every tab an icon beside its label, each its own", async () => {
    await renderScreen(<TabsLayout />);
    const icons = ["index", "jobs", "courses", "matches", "me"].map((name) => {
      const draw = shown[name].tabBarIcon as (p: { color: string; size: number }) => { props: { name: string } };
      return draw({ color: "black", size: 24 }).props.name;
    });
    expect(icons).toEqual(["Home", "Briefcase", "BookOpen", "Target", "User"]);
    expect(shown.skills.tabBarIcon).toBeUndefined();
  });

  it("draws the count as a badge on Me when there are new updates, and says it aloud too", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 4 }) });
    await renderScreen(<TabsLayout />);
    await waitFor(() => expect(shown.me.tabBarBadge).toBe(4));
    expect(shown.me.tabBarAccessibilityLabel).toBe("Me, 4 unread");
    // The label stays the plain word: the number is drawn once, in the badge.
    expect(shown.me.tabBarLabel).toBeUndefined();
    expect(shown.me.title).toBe("Me");
  });

  it("caps a large count at 99+ and keeps the exact number in the spoken name", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 150 }) });
    await renderScreen(<TabsLayout />);
    await waitFor(() => expect(shown.me.tabBarBadge).toBe("99+"));
    expect(shown.me.tabBarAccessibilityLabel).toBe("Me, 150 unread");
  });

  it("shows no number when everything is read", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 0 }) });
    await renderScreen(<TabsLayout />);
    // The count was asked for and answered 0: only then is "no number" a fact about the answer.
    await waitFor(() => expect(api.GET.mock.calls.map((c) => c[0])).toContain("/me/notifications/unread-count"));
    await settle();
    expect(shown.me.tabBarBadge).toBeUndefined();
    expect(shown.me.tabBarAccessibilityLabel).toBe("Me");
  });

  it("asks nothing of the server for somebody signed out", async () => {
    await renderScreen(<TabsLayout />);
    await settle();
    expect(api.GET).not.toHaveBeenCalled();
    expect(shown.me.tabBarBadge).toBeUndefined();
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
