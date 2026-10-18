import { fireEvent, screen } from "@testing-library/react-native";

import Home from "../../app/(tabs)/index";
import {
  account,
  api,
  application,
  matchItem,
  ok,
  profile,
  resetWorld,
  router,
  serve,
  world,
} from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

const page = (items: unknown[], has_skills = true) => ({ items, total: items.length, has_skills });
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString();

/** What a signed-in seeker's request table looks like: every personal query the home reads. */
function seeker(over: Record<string, unknown> = {}) {
  serve(api.GET, {
    "/auth/me": ok(account()),
    "/me/matches": ok(page([matchItem(1), matchItem(2)])),
    "/me/profile": ok(profile()),
    "/me/notifications/unread-count": ok({ unread: 0 }),
    "/me/applications": ok([]),
    ...over,
  });
}

/** Sprint 70, UI-19: the home is the person's own, not the signed-out one with a sentence added. */
describe("a job seeker's home", () => {
  it("leads with their best match and the sentence about it", async () => {
    seeker();
    await renderScreen(<Home />);
    expect(await screen.findByText("Your best match")).toBeTruthy();
    expect(screen.getByText("Ward assistant 1")).toBeTruthy();
    expect(screen.queryByText("Ward assistant 2")).toBeNull(); // one, not the list
    expect(screen.getByText("79% match")).toBeTruthy();
    expect(
      screen.getByText("You have 1 of 3 skills this job asks for. Missing: Infection control, Bed making."),
    ).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Open this match" }));
    expect(router.push).toHaveBeenCalledWith("/match/ward-assistant-1");
  });

  it("does not offer to apply from here (the consent step names the employer, which this summary lacks)", async () => {
    seeker();
    await renderScreen(<Home />);
    await screen.findByText("Your best match");
    expect(screen.queryByRole("button", { name: "Apply for this job" })).toBeNull();
  });

  it("says how complete the profile is and what to add next", async () => {
    seeker();
    await renderScreen(<Home />);
    expect(await screen.findByText("Profile 60% complete")).toBeTruthy();
    expect(screen.getByText("Add your skills next")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Profile 60% complete. Add your skills next" }));
    expect(router.push).toHaveBeenCalledWith("/profile");
  });

  it("has no next step for a finished profile", async () => {
    seeker({ "/me/profile": ok(profile({ completeness: { percent: 100, missing: [] } })) });
    await renderScreen(<Home />);
    expect(await screen.findByText("Profile 100% complete")).toBeTruthy();
    expect(screen.queryByText(/next$/)).toBeNull();
  });

  it("shows the new updates, in the label and for a screen reader, and nothing when there are none", async () => {
    seeker({ "/me/notifications/unread-count": ok({ unread: 3 }) });
    await renderScreen(<Home />);
    const button = await screen.findByRole("button", { name: /Updates: 3 new updates/ });
    expect(screen.getByText("3", { includeHiddenElements: true })).toBeTruthy(); // drawn in the pill too
    await fireEvent.press(button);
    expect(router.push).toHaveBeenCalledWith("/notices");
  });

  it("says nothing of updates when there are none", async () => {
    seeker();
    await renderScreen(<Home />);
    await screen.findByText("Your best match");
    expect(screen.queryByRole("button", { name: /Updates/ })).toBeNull();
  });

  it("counts the applications an employer has acted on lately, and links to them", async () => {
    seeker({
      "/me/applications": ok([
        application(1, { status: "shortlisted", updated_at: daysAgo(2) }),
        application(2, { status: "applied" }),
        application(3, { status: "rejected", updated_at: daysAgo(60) }),
        application(4, { status: "hired", updated_at: daysAgo(1) }),
      ]),
    });
    await renderScreen(<Home />);
    const button = await screen.findByRole("button", { name: "2 applications have news" });
    await fireEvent.press(button);
    expect(router.push).toHaveBeenCalledWith("/applications");
  });

  it("says nothing of applications when none has news", async () => {
    seeker({ "/me/applications": ok([application(1, { status: "applied" })]) });
    await renderScreen(<Home />);
    await screen.findByText("Your best match");
    expect(screen.queryByRole("button", { name: /have news|has news/ })).toBeNull();
  });

  it("asks for skills, not for a match, when none are declared", async () => {
    seeker({ "/me/matches": ok(page([], false)) });
    await renderScreen(<Home />);
    expect(await screen.findByText(/Add a few skills to your profile/)).toBeTruthy();
    expect(screen.queryByText("Your best match")).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "Go to my profile" }));
    expect(router.push).toHaveBeenCalledWith("/profile");
  });

  it("says there is no match yet, rather than nothing, when skills are declared and nothing fits", async () => {
    seeker({ "/me/matches": ok(page([], true)) });
    await renderScreen(<Home />);
    expect(await screen.findByText(/No match yet/)).toBeTruthy();
  });

  it("shows a placeholder, never a claim, while the matches are on their way", async () => {
    let answer!: (v: unknown) => void;
    seeker({ "/me/matches": () => new Promise((resolve) => (answer = resolve)) });
    await renderScreen(<Home />);
    // The account answers first (it decides whether there is a personal home at all), then the matches are awaited.
    expect(await screen.findByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText(/No match yet/)).toBeNull();
    expect(screen.queryByText("Your best match")).toBeNull();
    answer(ok(page([matchItem(1)])));
    await settle();
  });

  it.each([
    ["/me/applications", "the applications"],
    ["/me/notifications/unread-count", "the unread count"],
    ["/me/profile", "the profile"],
  ])("waits for %s too, so the block arrives once and not in pieces (Sprint 83)", async (path) => {
    let answer!: (v: unknown) => void;
    seeker({ [path]: () => new Promise((resolve) => (answer = resolve)) });
    await renderScreen(<Home />);
    await screen.findByLabelText("Loading");
    await settle();
    // The other three have answered; none of their parts is shown until this one has too.
    expect(screen.getAllByLabelText("Loading")).toHaveLength(1);
    expect(screen.queryByText("Your best match")).toBeNull();
    expect(screen.queryByText(/Profile \d+% complete/)).toBeNull();
    answer(ok(path === "/me/profile" ? profile() : path === "/me/applications" ? [] : { unread: 0 }));
    expect(await screen.findByText("Your best match")).toBeTruthy();
    expect(screen.queryByLabelText("Loading")).toBeNull();
  });

  it("is a failed part that does not hold the rest back for ever", async () => {
    seeker({ "/me/applications": () => Promise.resolve({ data: undefined, error: {}, response: { status: 500 } }) });
    await renderScreen(<Home />);
    expect(await screen.findByText("Your best match")).toBeTruthy();
  });

  it("holds the same height before and after it loads, so the search below does not move", async () => {
    const heightOf = (node: { props: { style?: unknown } }) => {
      const style = node.props.style;
      const flat = Array.isArray(style) ? Object.assign({}, ...style.flat(Infinity)) : (style as Record<string, unknown>);
      return (flat.minHeight ?? flat.height) as number;
    };
    let answer!: (v: unknown) => void;
    seeker({ "/me/matches": () => new Promise((resolve) => (answer = resolve)) });
    await renderScreen(<Home />);
    const placeholder = await screen.findByLabelText("Loading");
    const before = heightOf(placeholder.children[0] as never);
    expect(before).toBeGreaterThan(0);
    answer(ok(page([matchItem(1)])));
    await screen.findByText("Your best match");
    expect(heightOf(screen.getByTestId("signed-in-home") as never)).toBe(before);
  });

  it("shows the profile, updates and news as rows in one group, in that order", async () => {
    seeker({
      "/me/notifications/unread-count": ok({ unread: 2 }),
      "/me/applications": ok([application(1, { status: "hired", updated_at: daysAgo(1) })]),
    });
    await renderScreen(<Home />);
    await screen.findByText("Your best match");
    const rows = screen.getAllByRole("button").map((b) => b.props.accessibilityLabel);
    const group = rows.filter((n: string) => /complete|Updates|news/.test(n));
    expect(group).toEqual([
      "Profile 60% complete. Add your skills next",
      "Updates: 2 new updates",
      "1 application has news",
    ]);
  });

  it("still has the search and the way to browse, below the person's own", async () => {
    seeker();
    await renderScreen(<Home />);
    await screen.findByText("Your best match");
    expect(screen.getByRole("button", { name: "Browse jobs" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });
});

describe("home for everyone else", () => {
  it("makes no personal request for an organisation owner, and says where to go instead", async () => {
    serve(api.GET, { "/auth/me": ok(account("organisation")) });
    await renderScreen(<Home />);
    expect(await screen.findByText(/This app is for job seekers/)).toBeTruthy();
    expect(api.GET.mock.calls.map((c) => c[0])).toEqual(["/auth/me"]);
    expect(screen.queryByText("Your best match")).toBeNull();
    // Nor a placeholder that would never be replaced: nothing here is on its way.
    expect(screen.queryByLabelText("Loading")).toBeNull();
  });

  it("is the signed-out home, with the invitation to sign in, for somebody signed out", async () => {
    world.signedIn = false;
    await renderScreen(<Home />);
    expect(screen.getByText("Sign in to see jobs and courses matched to what you can do.")).toBeTruthy();
    expect(screen.queryByText("Your best match")).toBeNull();
    expect(api.GET).not.toHaveBeenCalled();
  });
});
