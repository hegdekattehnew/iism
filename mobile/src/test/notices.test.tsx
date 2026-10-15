import { fireEvent, screen } from "@testing-library/react-native";

import Notices from "../../app/notices";
import { account, api, failed, ok, push, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);
jest.mock("../push", () => require("./mocks").pushModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

const notice = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `n${n}`,
  template: "application_status_changed",
  payload: { vacancy: `Ward assistant ${n}`, organisation: "Apollo Care", status: "shortlisted", path: "/applications" },
  created_at: "2026-10-14T20:00:00+00:00",
  read_at: null,
  ...extra,
});

const served = (notices: unknown[], more: Record<string, unknown> = {}) =>
  serve(api.GET, { "/auth/me": ok(account()), "/me/notifications": ok(notices), ...more });
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));

describe("my updates", () => {
  it("asks a signed-out person to sign in and makes no request", async () => {
    world.signedIn = false;
    await renderScreen(<Notices />);
    await settle();
    expect(screen.getByText("Sign in to see your updates.")).toBeTruthy();
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("puts each notice into the website's own words, with the day in India", async () => {
    served([notice(1)]);
    await renderScreen(<Notices />);
    expect(
      await screen.findByText("Apollo Care moved your application for Ward assistant 1 to: Shortlisted."),
    ).toBeTruthy();
    expect(screen.getByText("15 Oct 2026")).toBeTruthy();
    expect(screen.getByText("1 unread")).toBeTruthy();
    expect(screen.getByText("New")).toBeTruthy();
  });

  it("says there are none yet", async () => {
    served([]);
    await renderScreen(<Notices />);
    expect(await screen.findByText(/Nothing yet/)).toBeTruthy();
  });

  it("opens the place a notice names, and marks it read on the way", async () => {
    served([notice(1)]);
    serve(api.POST, { "/me/notifications/{notification_id}/read": ok(undefined) });
    await renderScreen(<Notices />);
    await press("Open");
    expect(router.push).toHaveBeenCalledWith("/applications");
    await settle();
    expect(api.POST.mock.calls[0]).toEqual([
      "/me/notifications/{notification_id}/read",
      { params: { path: { notification_id: "n1" } } },
    ]);
  });

  it("offers no Open for a notice that names nowhere, and never follows a path off the app", async () => {
    served([notice(1, { payload: { vacancy: "V", path: "https://evil.example" } }), notice(2, { payload: { vacancy: "V" } })]);
    await renderScreen(<Notices />);
    await screen.findByText("2 unread");
    expect(screen.queryByRole("button", { name: "Open" })).toBeNull();
  });

  it("marks one, or all, as read", async () => {
    served([notice(1), notice(2, { read_at: "2026-10-15T01:00:00Z" })]);
    serve(api.POST, {
      "/me/notifications/{notification_id}/read": ok(undefined),
      "/me/notifications/read": ok({ marked: 1 }),
    });
    await renderScreen(<Notices />);
    await press("Mark as read");
    await settle();
    expect(api.POST.mock.calls[0][1]).toEqual({ params: { path: { notification_id: "n1" } } });
    await press("Mark all as read");
    await settle();
    expect(api.POST.mock.calls[1][0]).toBe("/me/notifications/read");
  });

  it("says when a read could not be done, and that the session ended on a 401", async () => {
    served([notice(1)]);
    serve(api.POST, { "/me/notifications/{notification_id}/read": failed(500) });
    await renderScreen(<Notices />);
    await press("Mark as read");
    expect(await screen.findByText("Could not do that. Try again.")).toBeTruthy();
  });

  it("says the session ended on a 401 when marking", async () => {
    served([notice(1)]);
    serve(api.POST, { "/me/notifications/{notification_id}/read": failed(401) });
    await renderScreen(<Notices />);
    await press("Mark as read");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("asks for the older ones with the last one's time and id, once a page is full", async () => {
    const page = Array.from({ length: 30 }, (_, i) => notice(i + 1, { id: `n${i + 1}`, created_at: `2026-09-${String(30 - (i % 28)).padStart(2, "0")}T10:00:00Z` }));
    served(page);
    await renderScreen(<Notices />);
    await press("Show older updates");
    await settle();
    const calls = api.GET.mock.calls.filter((c) => c[0] === "/me/notifications");
    expect(calls).toHaveLength(2);
    const second = (calls[1][1] as { params: { query: Record<string, unknown> } }).params.query;
    expect(second.before_id).toBe("n30");
    expect(second.before).toBe(page[29].created_at);
  });

  it("does not offer older ones when the first page was short", async () => {
    served([notice(1)]);
    await renderScreen(<Notices />);
    await screen.findByText("1 unread");
    expect(screen.queryByRole("button", { name: "Show older updates" })).toBeNull();
  });

  it("says the session ended on a 401, not that it could not load", async () => {
    served([], { "/me/notifications": failed(401) });
    await renderScreen(<Notices />);
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });
});

describe("asking to send notifications", () => {
  it("asks here, in context, with what a notification will and will not say", async () => {
    served([notice(1)]);
    await renderScreen(<Notices />);
    expect(await screen.findByText("Get updates on your phone")).toBeTruthy();
    expect(screen.getByText(/never shows your name, your phone number or what an employer wrote/)).toBeTruthy();
  });

  it("turns them on, and registers this phone once they are allowed", async () => {
    served([notice(1)]);
    await renderScreen(<Notices />);
    await press("Turn on notifications");
    await settle();
    expect(push.ask).toHaveBeenCalledTimes(1);
    expect(push.register).toHaveBeenCalledTimes(1);
  });

  it("lets the person say not now, and does not ask again", async () => {
    served([notice(1)]);
    await renderScreen(<Notices />);
    await press("Not now");
    expect(push.decline).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["already allowed", { permission: "granted" as const, declined: false }],
    ["refused at the system, which will not ask twice", { permission: "denied" as const, declined: false }],
    ["a person who chose not now", { permission: "undetermined" as const, declined: true }],
  ])("does not ask: %s", async (_why, state) => {
    Object.assign(push, state);
    served([notice(1)]);
    await renderScreen(<Notices />);
    await screen.findByText("1 unread");
    expect(screen.queryByText("Get updates on your phone")).toBeNull();
  });
});
