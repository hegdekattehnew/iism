import {
  canDelete,
  confirmConsent,
  consentOf,
  consentPrompt,
  exportFile,
  fetchConsent,
  withdrawConsent,
  type DeletionPreview,
} from "./account";
import { ApiError } from "./errors";

const fate = (name: string) => ({ slug: name.toLowerCase(), name, listings: 2 });

describe("the file a person takes away", () => {
  it("is named for what it is and the day, and is the whole document, indented", () => {
    const file = exportFile({ account: { id: "u1" }, devices: [{ platform: "ios" }] }, "2026-10-15");
    expect(file.filename).toBe("iism-my-data-2026-10-15.json");
    expect(JSON.parse(file.text)).toEqual({ account: { id: "u1" }, devices: [{ platform: "ios" }] });
    expect(file.text).toContain("\n  ");
  });

  it("is exactly what the server said, so a token the server never sent cannot appear", () => {
    const server = { devices: [{ platform: "android", locale: "en" }] };
    expect(exportFile(server, "2026-10-15").text).not.toContain("token");
  });
});

describe("deleting the account", () => {
  const preview = (over: Partial<DeletionPreview> = {}): DeletionPreview => ({
    organisations_deleted: [],
    blocked_by: [],
    ...over,
  });

  it("may go ahead when nothing blocks it", () => {
    expect(canDelete(preview())).toBe(true);
    expect(canDelete(preview({ organisations_deleted: [fate("Apollo")] }))).toBe(true);
  });

  it("may not while the person is the only owner of an organisation others belong to", () => {
    expect(canDelete(preview({ blocked_by: [fate("Apollo")] }))).toBe(false);
  });
});

describe("what was agreed to", () => {
  it("names the notice version and when, once both are recorded", () => {
    expect(consentOf({ consent_version: "2026-09-11", consented_at: "2026-10-01T10:00:00Z" })).toEqual({
      version: "2026-09-11",
      at: "2026-10-01T10:00:00Z",
    });
  });

  it("says nothing was recorded rather than inventing it", () => {
    expect(consentOf({})).toBeNull();
    expect(consentOf({ consent_version: "2026-09-11", consented_at: null })).toBeNull();
  });
});

describe("consent (Sprint 72)", () => {
  const state = { withdrawn: false, current: true, live_applications: 1, live_interests: 0 };
  const fake = (answer: unknown, status = 200) =>
    ({
      GET: jest.fn(async () => ({ data: status < 400 ? answer : undefined, error: status < 400 ? undefined : answer, response: { status } })),
      POST: jest.fn(async () => ({ data: status < 400 ? answer : undefined, error: status < 400 ? undefined : answer, response: { status } })),
    }) as never;

  it("reads where the person stands, and what withdrawing would take back", async () => {
    expect(await fetchConsent(fake(state))).toEqual(state);
  });

  it("withdraws, and returns the server's new state whole", async () => {
    const api = fake({ ...state, withdrawn: true });
    expect((await withdrawConsent(api)).withdrawn).toBe(true);
    expect((api as { POST: jest.Mock }).POST).toHaveBeenCalledWith("/me/account/consent/withdraw");
  });

  it("confirms with the version it is given and keeps the server's refusal", async () => {
    const ok = fake(state);
    await confirmConsent(ok, "2026-10-17");
    expect((ok as { POST: jest.Mock }).POST).toHaveBeenCalledWith("/me/account/consent", {
      body: { consent_version: "2026-10-17" },
    });
    await expect(confirmConsent(fake({ detail: "consent_required" }, 422), "1999")).rejects.toMatchObject({
      status: 422,
      detail: "consent_required",
    });
    await expect(confirmConsent(fake({ detail: "x" }, 422), "1999")).rejects.toBeInstanceOf(ApiError);
  });

  it("prompts for a stale notice and a withdrawal, never for a current one or for none on record", () => {
    expect(consentPrompt({ consent_version: "2026-10-17", consent_current: true, consent_withdrawn: false })).toBeNull();
    expect(consentPrompt({ consent_version: "2026-09-11", consent_current: false, consent_withdrawn: false })).toBe("stale");
    expect(consentPrompt({ consent_version: null, consent_current: false, consent_withdrawn: false })).toBeNull();
    expect(consentPrompt({ consent_version: "2026-10-17", consent_current: true, consent_withdrawn: true })).toBe("paused");
    expect(consentPrompt({})).toBeNull(); // an older server that does not say
  });
});
