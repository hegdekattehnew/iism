import { fireEvent, screen } from "@testing-library/react-native";
import { Linking, Share } from "react-native";

import Account from "../../app/account";
import { account, api, failed, ok, resetWorld, router, serve, tokens, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

const share = jest.spyOn(Share, "share");
const open = jest.spyOn(Linking, "openURL");

beforeEach(() => {
  resetWorld();
  share.mockReset().mockResolvedValue({ action: "sharedAction" } as never);
  open.mockReset().mockResolvedValue(true as never);
  world.signedIn = true;
});

const me = (extra: Record<string, unknown> = {}) => ({
  ...account(),
  consent_version: "2026-09-11",
  consented_at: "2026-10-01T10:00:00+00:00",
  ...extra,
});
/** What `GET /me/account/consent` says (Sprint 72): agreed to the notice in force, nothing withdrawn. */
const consentState = (extra: Record<string, unknown> = {}) => ({
  consent_version: "2026-10-24",
  consented_at: "2026-10-01T10:00:00+00:00",
  notice_version: "2026-10-24",
  current: true,
  withdrawn: false,
  consent_withdrawn_at: null,
  live_applications: 0,
  live_interests: 0,
  ...extra,
});
const served = (more: Record<string, unknown> = {}, consent: Record<string, unknown> = {}) =>
  serve(api.GET, {
    "/auth/me": ok(me()),
    "/me/account/consent": ok(consentState(consent)),
    ...more,
  });
/**
 * The button's own state. `toBeDisabled` also passes for anything inside a `Card`, which is itself a
 * disabled `Pressable` when it has no `onPress`, so on its own it cannot tell this button's state.
 */
const disabled = (button: { props: { accessibilityState?: { disabled?: boolean } } }) =>
  button.props.accessibilityState?.disabled === true;
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));

describe("the account, signed out", () => {
  it("asks to sign in and makes no request", async () => {
    world.signedIn = false;
    await renderScreen(<Account />);
    await settle();
    expect(screen.getByText("Sign in to see your account.")).toBeTruthy();
    expect(api.GET).not.toHaveBeenCalled();
    await press("Sign in");
    expect(router.push).toHaveBeenCalledWith("/sign-in");
  });
});

describe("what you agreed to", () => {
  it("names the notice and the day, and opens the privacy notice on the website", async () => {
    served();
    await renderScreen(<Account />);
    expect(await screen.findByText("You agreed to the privacy notice of 2026-10-24 on 1 Oct 2026.")).toBeTruthy();
    await press("Read the privacy notice");
    expect(open).toHaveBeenCalledWith("http://localhost:3000/en/privacy");
  });

  it("says no consent is recorded rather than inventing one", async () => {
    served({}, { consent_version: null, consented_at: null });
    await renderScreen(<Account />);
    expect(await screen.findByText(/No consent is recorded for this account/)).toBeTruthy();
  });
});

describe("withdrawing consent, and coming back (Sprint 72)", () => {
  const withdrawn = { withdrawn: true, consent_withdrawn_at: "2026-10-05T08:00:00+00:00" };

  it("shows who holds the person's details before the button that ends it, and changes nothing by looking", async () => {
    served({}, { live_applications: 2, live_interests: 1 });
    await renderScreen(<Account />);
    expect(await screen.findByText(/This is a pause, not an erasure/)).toBeTruthy();
    await press("Withdraw my consent…");
    expect(await screen.findByText(/takes back 2 applications and 1 course interest/)).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("says plainly when nobody holds them", async () => {
    served();
    await renderScreen(<Account />);
    await press("Withdraw my consent…");
    expect(await screen.findByText(/No employer or training provider holds your contact/)).toBeTruthy();
  });

  it("withdraws on confirmation, and the screen then offers to come back instead", async () => {
    served();
    serve(api.POST, { "/me/account/consent/withdraw": ok(consentState(withdrawn)) });
    await renderScreen(<Account />);
    await press("Withdraw my consent…");
    serve(api.GET, {
      "/auth/me": ok(me()),
      "/me/account/consent": ok(consentState(withdrawn)),
    });
    await press("Withdraw my consent");
    await settle();
    expect(api.POST.mock.calls.map((c) => c[0])).toEqual(["/me/account/consent/withdraw"]);
    expect(await screen.findByText(/You withdrew your consent on 5 Oct 2026/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw my consent…" })).toBeNull();
    expect(screen.getByRole("button", { name: "Confirm and switch my account back on" })).toBeTruthy();
  });

  it("restores by confirming the notice this build shows, and sends that version", async () => {
    served({}, withdrawn);
    serve(api.POST, { "/me/account/consent": ok(consentState()) });
    await renderScreen(<Account />);
    await press("Confirm and switch my account back on");
    await settle();
    expect(api.POST).toHaveBeenCalledWith("/me/account/consent", { body: { consent_version: "2026-10-24" } });
  });

  it("asks a person whose notice changed to read and confirm, and blocks nothing", async () => {
    served({}, { current: false, consent_version: "2026-09-11" });
    await renderScreen(<Account />);
    expect(await screen.findByText("The privacy notice has changed")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw my consent…" })).toBeTruthy();
    await press("I have read it and I am 18 or over");
    await settle();
    expect(api.POST).toHaveBeenCalledWith("/me/account/consent", { body: { consent_version: "2026-10-24" } });
  });

  it("shows the server's sentence when withdrawing is refused, and that the session ended on a 401", async () => {
    served();
    serve(api.POST, { "/me/account/consent/withdraw": failed(401) });
    await renderScreen(<Account />);
    await press("Withdraw my consent…");
    await press("Withdraw my consent");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("reads a refusal to withdraw and says nothing changed", async () => {
    served();
    serve(api.POST, { "/me/account/consent/withdraw": failed(500, "boom") });
    await renderScreen(<Account />);
    await press("Withdraw my consent…");
    await press("Withdraw my consent");
    expect(await screen.findByText(/boom|could not be withdrawn/)).toBeTruthy();
  });
});

describe("taking your data with you", () => {
  it("fetches the whole document and hands it to the share sheet as text", async () => {
    served({ "/me/account/export": ok({ account: { id: "u1" }, devices: [{ platform: "android" }] }) });
    await renderScreen(<Account />);
    await press("Download my data");
    await settle();
    expect(share).toHaveBeenCalledTimes(1);
    const arg = share.mock.calls[0][0] as { title: string; message: string };
    expect(arg.title).toBe("My IISM data");
    expect(JSON.parse(arg.message)).toEqual({ account: { id: "u1" }, devices: [{ platform: "android" }] });
  });

  it("says when the export could not be prepared, and that the session ended on a 401", async () => {
    served({ "/me/account/export": failed(500) });
    await renderScreen(<Account />);
    await press("Download my data");
    expect(await screen.findByText("The download could not be prepared. Try again.")).toBeTruthy();
  });

  it("says the session ended on a 401", async () => {
    served({ "/me/account/export": failed(401) });
    await renderScreen(<Account />);
    await press("Download my data");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("says when the share sheet could not open", async () => {
    share.mockRejectedValue(new Error("no handler") as never);
    served({ "/me/account/export": ok({ account: {} }) });
    await renderScreen(<Account />);
    await press("Download my data");
    expect(await screen.findByText("Could not open the share sheet. Try again.")).toBeTruthy();
  });
});

describe("leaving", () => {
  const preview = (organisations_deleted: unknown[] = [], blocked_by: unknown[] = []) =>
    ({ "/me/account/deletion": ok({ organisations_deleted, blocked_by }) }) as Record<string, unknown>;
  const fate = (name: string) => ({ slug: name.toLowerCase(), name, listings: 2 });

  it("asks nothing of the server, and deletes nothing, until the person says they might", async () => {
    served(preview());
    await renderScreen(<Account />);
    await screen.findByText("Delete your account");
    expect(api.GET.mock.calls.map((c) => c[0])).not.toContain("/me/account/deletion");
    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("shows what would go with the account before the act", async () => {
    served(preview([fate("Sunrise")]));
    await renderScreen(<Account />);
    await press("Delete my account…");
    expect(await screen.findByText(/These organisations have no other members/)).toBeTruthy();
    expect(screen.getByText("Sunrise — 2 listings")).toBeTruthy();
    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("says plainly when nothing else goes with it", async () => {
    served(preview());
    await renderScreen(<Account />);
    await press("Delete my account…");
    expect(await screen.findByText(/Nothing else goes with it/)).toBeTruthy();
  });

  it("cannot be confirmed while the person is the only owner of an organisation others belong to", async () => {
    served(preview([], [fate("Apollo")]));
    await renderScreen(<Account />);
    await press("Delete my account…");
    expect(await screen.findByText(/You are the only owner of an organisation/)).toBeTruthy();
    expect(disabled(screen.getByRole("button", { name: "Delete permanently" }))).toBe(true);
  });

  it("cannot be confirmed before the preview has arrived", async () => {
    served({ "/me/account/deletion": new Promise(() => undefined) });
    await renderScreen(<Account />);
    await press("Delete my account…");
    await screen.findByText("Checking what goes with it…");
    expect(disabled(screen.getByRole("button", { name: "Delete permanently" }))).toBe(true);
  });

  it("deletes, forgets this phone's session, and goes home", async () => {
    served(preview());
    serve(api.DELETE, { "/me/account": ok(undefined) });
    await renderScreen(<Account />);
    await press("Delete my account…");
    // The button is disabled until the preview has arrived: wait for it, or the press does nothing.
    await screen.findByText(/Nothing else goes with it/);
    await press("Delete permanently");
    await settle();
    expect(api.DELETE).toHaveBeenCalledTimes(1);
    expect(tokens.clear).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith("/");
  });

  it("keeps the session when the deletion fails, and says what the server said", async () => {
    served(preview());
    serve(api.DELETE, { "/me/account": failed(409, "Make somebody else an owner of Apollo before deleting your account") });
    await renderScreen(<Account />);
    await press("Delete my account…");
    // The button is disabled until the preview has arrived: wait for it, or the press does nothing.
    await screen.findByText(/Nothing else goes with it/);
    await press("Delete permanently");
    expect(await screen.findByText(/Make somebody else an owner of Apollo/)).toBeTruthy();
    expect(tokens.clear).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("says the session ended on a 401, not that the deletion failed", async () => {
    served(preview());
    serve(api.DELETE, { "/me/account": failed(401) });
    await renderScreen(<Account />);
    await press("Delete my account…");
    // The button is disabled until the preview has arrived: wait for it, or the press does nothing.
    await screen.findByText(/Nothing else goes with it/);
    await press("Delete permanently");
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    expect(tokens.clear).not.toHaveBeenCalled();
  });

  it("can be cancelled, and nothing is deleted", async () => {
    served(preview());
    await renderScreen(<Account />);
    await press("Delete my account…");
    await press("Cancel");
    expect(await screen.findByRole("button", { name: "Delete my account…" })).toBeTruthy();
    expect(api.DELETE).not.toHaveBeenCalled();
  });
});
