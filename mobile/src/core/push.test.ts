import { deviceBody, pathFromPush, shouldAsk, shouldRegister, type AskState } from "./push";

const ready: AskState = { signedIn: true, isJobSeeker: true, permission: "undetermined", declined: false };

describe("when to ask for permission", () => {
  it("asks a signed-in job seeker who has not been asked", () => {
    expect(shouldAsk(ready)).toBe(true);
  });

  it.each([
    ["signed out", { signedIn: false }],
    ["an account that is not a job seeker", { isJobSeeker: false }],
    ["an account not yet known", { isJobSeeker: undefined }],
    ["already allowed", { permission: "granted" as const }],
    ["already refused by the system, which will not ask twice", { permission: "denied" as const }],
    ["a person who chose not now", { declined: true }],
  ])("does not ask: %s", (_why, change) => {
    expect(shouldAsk({ ...ready, ...change })).toBe(false);
  });
});

describe("when to register a token without asking", () => {
  it("registers once allowed, for a signed-in job seeker", () => {
    expect(shouldRegister({ signedIn: true, isJobSeeker: true, permission: "granted" })).toBe(true);
  });

  it.each([
    [{ signedIn: false }],
    [{ isJobSeeker: false }],
    [{ isJobSeeker: undefined }],
    [{ permission: "undetermined" as const }],
    [{ permission: "denied" as const }],
  ])("does not register: %j", (change) => {
    expect(shouldRegister({ signedIn: true, isJobSeeker: true, permission: "granted", ...change })).toBe(false);
  });
});

describe("what is sent and where a tap goes", () => {
  it("sends the token, the platform and the language, nothing else", () => {
    expect(deviceBody("ExponentPushToken[x]", "android", "hi")).toEqual({
      token: "ExponentPushToken[x]",
      platform: "android",
      locale: "hi",
    });
  });

  it("opens the in-app place a push names, through the one link table", () => {
    expect(pathFromPush({ template: "job_alert", path: "/jobs/ward-assistant-1" })).toBe("/job/ward-assistant-1");
    expect(pathFromPush({ path: "/applications" })).toBe("/applications");
    expect(pathFromPush({ path: "/notifications" })).toBe("/notices");
  });

  it("opens nothing for a push with no path or a path that leaves the app", () => {
    for (const data of [null, undefined, "x", 5, {}, { path: 5 }, { path: "//evil.example" }, { path: "https://evil.example" }, { path: "/ops/queue" }]) {
      expect(pathFromPush(data)).toBeNull();
    }
  });
});
