import { createApi } from "./api";
import { ApiError } from "./errors";
import {
  BODY_MAX,
  BODY_MIN,
  KINDS,
  canSend,
  kindsFor,
  listMyMessages,
  messageBody,
  sendFailure,
  sendMessage,
  type MessageDraft,
} from "./grievance";
import { createTokenStore, type SecretBackend } from "./token-store";

const nothing: SecretBackend = { read: async () => null, write: async () => undefined, remove: async () => undefined };

function harness(answer: (path: string, body: unknown) => Response) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    const text = await request.clone().text();
    const body = text ? JSON.parse(text) : undefined;
    calls.push({ method: request.method, path: new URL(request.url).pathname, body });
    return answer(new URL(request.url).pathname, body);
  }) as typeof fetch;
  return {
    calls,
    api: createApi({
      baseUrl: "https://api.test",
      tokens: createTokenStore(nothing),
      locale: () => "en",
      appVersion: "1.0.0",
      platform: "android",
      onUpgradeRequired: () => undefined,
      fetch: fetcher,
    }),
  };
}
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

const draft = (over: Partial<MessageDraft> = {}): MessageDraft => ({
  kind: "contact",
  body: "I have a question about how my data is used.",
  replyTo: "",
  signedIn: true,
  ...over,
});

describe("what a person may choose", () => {
  it("offers a request about your own data only to an account", () => {
    expect(kindsFor(true)).toEqual(["contact", "grievance", "data_request"]);
    expect(kindsFor(false)).toEqual(["contact", "grievance"]);
    expect(KINDS).toHaveLength(3);
  });
});

describe("when a message can be sent", () => {
  it("needs enough words", () => {
    expect(canSend(draft({ body: "x".repeat(BODY_MIN - 1) }))).toBe(false);
    expect(canSend(draft({ body: " ".repeat(40) }))).toBe(false);
    expect(canSend(draft({ body: "x".repeat(BODY_MIN) }))).toBe(true);
    expect(canSend(draft({ body: "x".repeat(BODY_MAX + 1) }))).toBe(false);
  });

  it("needs an address to answer at, for a stranger and not for an account", () => {
    expect(canSend(draft({ signedIn: false, replyTo: "" }))).toBe(false);
    expect(canSend(draft({ signedIn: false, replyTo: "  " }))).toBe(false);
    expect(canSend(draft({ signedIn: false, replyTo: "asha@example.org" }))).toBe(true);
    expect(canSend(draft({ signedIn: true, replyTo: "" }))).toBe(true);
  });

  it("refuses a request about data from somebody signed out", () => {
    expect(canSend(draft({ kind: "data_request", signedIn: false, replyTo: "a@b.org" }))).toBe(false);
    expect(canSend(draft({ kind: "data_request", signedIn: true }))).toBe(true);
  });
});

describe("what is sent", () => {
  it("trims, sends the honeypot empty, and gives a signed-in person no address to fill", () => {
    expect(messageBody(draft({ body: "  a question here, please  ", replyTo: "ignored@x.org" }))).toEqual({
      kind: "contact",
      body: "a question here, please",
      reply_to: undefined,
      website: "",
    });
  });

  it("gives a stranger's address, trimmed", () => {
    expect(messageBody(draft({ signedIn: false, replyTo: " asha@example.org " })).reply_to).toBe("asha@example.org");
  });

  it("posts it and returns the reference", async () => {
    const { api, calls } = harness(() => json(201, { reference: "G-1", kind: "contact", acknowledge_within_hours: 24, resolve_within_days: 15 }));
    expect((await sendMessage(api, draft())).reference).toBe("G-1");
    expect(calls[0]).toMatchObject({ method: "POST", path: "/grievances" });
    expect((calls[0].body as { website: string }).website).toBe("");
  });

  it("reads how long to wait from a refusal, and keeps the server's sentence otherwise", async () => {
    const { api } = harness(() => json(429, { detail: "Too many" }, { "retry-after": "42" }));
    await expect(sendMessage(api, draft())).rejects.toMatchObject({ status: 429, retryAfter: 42 });
    const other = harness(() => json(422, { detail: "Write at least 10 characters." }));
    await expect(sendMessage(other.api, draft())).rejects.toMatchObject({ status: 422, detail: "Write at least 10 characters." });
  });

  it("lists what a person has sent, with where each stands", async () => {
    const { api, calls } = harness(() => json(200, [{ reference: "G-1", kind: "grievance", status: "acknowledged", created_at: "x" }]));
    expect((await listMyMessages(api))[0].status).toBe("acknowledged");
    expect(calls[0].path).toBe("/me/grievances");
  });
});

describe("what to say when it fails", () => {
  it("says how long to wait, to sign in, or what the server said", () => {
    expect(sendFailure(new ApiError(429, null, 42))).toEqual({ key: "errorWait", seconds: 42 });
    expect(sendFailure(new ApiError(429, null, 0))).toEqual({ key: "errorWait", seconds: 60 });
    expect(sendFailure(new ApiError(401, null))).toEqual({ key: "errorSignIn" });
    expect(sendFailure(new ApiError(422, "Give an email address."))).toEqual({ key: "errorGeneric", detail: "Give an email address." });
    expect(sendFailure(new Error("network"))).toEqual({ key: "errorGeneric", detail: null });
  });
});
