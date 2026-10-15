import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react-native";
import type { ReactNode } from "react";

import { meKeys } from "../core/me-keys";
import {
  useAddSkills,
  useApply,
  useReadAll,
  useReadOne,
  useSendMessage,
  useUnreadCount,
  UNREAD_POLL_MS,
  useRegisterInterest,
  useRemoveSkill,
  useToggleSave,
  useUpdateProfile,
  useWithdraw,
  useWithdrawInterest,
} from "../lib/me-queries";
import { account, api, application, interest, ok, profile, resetWorld, serve, world } from "./mocks";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => {
  resetWorld();
  world.signedIn = true;
});

/** A client holding one answer under every personal key, so what a write refreshes can be seen. */
function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { gcTime: Infinity } } });
  for (const key of [
    meKeys.profile,
    meKeys.matches,
    meKeys.match("ward-assistant-1"),
    meKeys.applications,
    meKeys.saved,
    meKeys.interests,
    meKeys.notices,
    meKeys.unread,
    meKeys.messages,
  ]) {
    qc.setQueryData(key, []);
  }
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  const stale = (key: readonly unknown[]) => qc.getQueryState(key)?.isInvalidated === true;
  return { qc, wrapper, stale };
}

const run = async (mutate: () => void) => {
  await act(async () => {
    mutate();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
};

describe("what a write refreshes", () => {
  it("changing skills makes the profile, every match and every open match stale: a skill moves every score", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, { "/me/profile/skills/bulk": ok(profile()) });
    const { result } = await renderHook(() => useAddSkills(), { wrapper });
    await run(() => result.current.mutate({ items: [{ skill_slug: "a", proficiency: 3 }], preferred_role_title: null }));
    expect(stale(meKeys.profile)).toBe(true);
    expect(stale(meKeys.matches)).toBe(true);
    expect(stale(meKeys.match("ward-assistant-1"))).toBe(true);
    expect(stale(meKeys.applications)).toBe(false);
  });

  it("removing a skill does the same", async () => {
    const { wrapper, stale } = setup();
    serve(api.DELETE, { "/me/profile/skills/{skill_slug}": ok(profile()) });
    const { result } = await renderHook(() => useRemoveSkill(), { wrapper });
    await run(() => result.current.mutate("a"));
    expect(stale(meKeys.matches)).toBe(true);
    expect(stale(meKeys.match("ward-assistant-1"))).toBe(true);
  });

  it("saving the basics refreshes the matches, since place and experience order and cap them", async () => {
    const { wrapper, stale } = setup();
    serve(api.PUT, { "/me/profile": ok(profile()) });
    const { result } = await renderHook(() => useUpdateProfile(), { wrapper });
    await run(() => result.current.mutate({ headline: "x" }));
    expect(stale(meKeys.matches)).toBe(true);
    expect(stale(meKeys.match("ward-assistant-1"))).toBe(true);
  });

  it("applying and withdrawing refresh the applications and nothing else", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, {
      "/me/applications": ok(application(1)),
      "/me/applications/{application_id}/withdraw": ok(application(1, { status: "withdrawn" })),
    });
    const apply = await renderHook(() => useApply(), { wrapper });
    await run(() => apply.result.current.mutate({ jobSlug: "ward-assistant-1", message: "" }));
    expect(stale(meKeys.applications)).toBe(true);
    expect(stale(meKeys.saved)).toBe(false);
    const withdraw = await renderHook(() => useWithdraw(), { wrapper });
    await run(() => withdraw.result.current.mutate("a1"));
    expect(stale(meKeys.interests)).toBe(false);
  });

  it("saving a vacancy refreshes the saved list", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, { "/me/saved-jobs": ok({}) });
    const { result } = await renderHook(() => useToggleSave(), { wrapper });
    await run(() => result.current.mutate({ slug: "ward-assistant-1", saved: false }));
    expect(stale(meKeys.saved)).toBe(true);
    expect(stale(meKeys.applications)).toBe(false);
  });

  it("registering and withdrawing interest refresh the interests", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, {
      "/me/course-interests": ok(interest(1)),
      "/me/course-interests/{interest_id}/withdraw": ok(interest(1, { status: "withdrawn" })),
    });
    const register = await renderHook(() => useRegisterInterest(), { wrapper });
    await run(() => register.result.current.mutate({ courseSlug: "phlebotomy-1", message: "" }));
    expect(stale(meKeys.interests)).toBe(true);
    const withdraw = await renderHook(() => useWithdrawInterest(), { wrapper });
    await run(() => withdraw.result.current.mutate("i1"));
    expect(stale(meKeys.applications)).toBe(false);
  });

  it("reading one notice or all refreshes the list and the count that the tab shows", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, {
      "/me/notifications/{notification_id}/read": ok(undefined),
      "/me/notifications/read": ok({ marked: 2 }),
    });
    const one = await renderHook(() => useReadOne(), { wrapper });
    await run(() => one.result.current.mutate("n1"));
    expect(stale(meKeys.notices)).toBe(true);
    expect(stale(meKeys.unread)).toBe(true);
    expect(stale(meKeys.applications)).toBe(false);
    const all = await renderHook(() => useReadAll(), { wrapper });
    await run(() => all.result.current.mutate());
    expect(stale(meKeys.unread)).toBe(true);
  });

  it("sending a message refreshes what the person has sent", async () => {
    const { wrapper, stale } = setup();
    serve(api.POST, { "/grievances": ok({ reference: "G-1", kind: "contact", acknowledge_within_hours: 24, resolve_within_days: 15 }) });
    const { result } = await renderHook(() => useSendMessage(), { wrapper });
    await run(() =>
      result.current.mutate({ kind: "contact", body: "a question about my data", replyTo: "", signedIn: true }),
    );
    expect(stale(meKeys.messages)).toBe(true);
    expect(stale(meKeys.notices)).toBe(false);
  });

  it("asks for the unread count again while the app is in front, and when it returns: the tab is mounted all session", async () => {
    world.signedIn = true;
    serve(api.GET, { "/auth/me": ok(account()), "/me/notifications/unread-count": ok({ unread: 1 }) });
    const { qc, wrapper } = setup();
    qc.clear();
    await renderHook(() => useUnreadCount(), { wrapper });
    await run(() => undefined);
    const query = qc.getQueryCache().find({ queryKey: meKeys.unread });
    expect(query?.observers[0].options.refetchInterval).toBe(UNREAD_POLL_MS);
    expect(query?.observers[0].options.refetchOnWindowFocus).toBe(true);
    expect(UNREAD_POLL_MS).toBeGreaterThanOrEqual(30_000);
  });
});
