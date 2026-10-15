/**
 * A message to the team: a question, a complaint, or a request about the person's own data. The
 * rules of the web's `MessageForm`, in one place and free of React Native, so they are tested in
 * Node (ADR-067).
 *
 * - **A request about your own data needs an account**, so the server knows it is you asking.
 * - **A stranger must give an address to be answered at**; a signed-in person is answered through
 *   their account and is never asked for one.
 * - **The honeypot is sent empty.** The field exists for a bot to fill; this app never shows it.
 * - **A refusal says how long to wait** when the server did (`Retry-After`).
 */

import type { components } from "../api/schema";
import type { Api } from "./api";
import { ApiError, readDetail, retryAfterSeconds } from "./errors";
import { unwrap } from "./public";

export type Kind = components["schemas"]["GrievanceIn"]["kind"];
export type MyMessage = components["schemas"]["GrievanceOut"];
export type Submitted = components["schemas"]["GrievanceSubmittedOut"];

export const BODY_MIN = 10;
export const BODY_MAX = 4000;
export const REPLY_MAX = 254;

/** Every kind, as a record keyed by the schema's own union: a new kind is a compile error here. */
const ALL: Record<Kind, true> = { contact: true, grievance: true, data_request: true };
export const KINDS = Object.keys(ALL) as Kind[];

/** What a person may choose: a data request only from an account. */
export const kindsFor = (signedIn: boolean): Kind[] =>
  KINDS.filter((kind) => kind !== "data_request" || signedIn);

export type MessageDraft = { kind: Kind; body: string; replyTo: string; signedIn: boolean };

/** Whether the draft can be sent: long enough, and an address to answer at for a stranger. */
export function canSend(draft: MessageDraft): boolean {
  const longEnough = draft.body.trim().length >= BODY_MIN && draft.body.length <= BODY_MAX;
  const answerable = draft.signedIn || draft.replyTo.trim().length > 0;
  const allowed = kindsFor(draft.signedIn).includes(draft.kind);
  return longEnough && answerable && allowed;
}

export function messageBody(draft: MessageDraft): components["schemas"]["GrievanceIn"] {
  return {
    kind: draft.kind,
    body: draft.body.trim(),
    // A signed-in person is answered through their account: never ask them for, or send, an address.
    reply_to: draft.signedIn ? undefined : draft.replyTo.trim(),
    website: "",
  };
}

export async function sendMessage(api: Api, draft: MessageDraft): Promise<Submitted> {
  const { data, error, response } = await api.POST("/grievances", { body: messageBody(draft) });
  const failure: unknown = error;
  if (failure !== undefined && failure !== null) {
    throw new ApiError(response.status, readDetail(failure), retryAfterSeconds(response));
  }
  if (!data) throw new ApiError(response.status, null);
  return data;
}

export async function listMyMessages(api: Api): Promise<MyMessage[]> {
  return unwrap(await api.GET("/me/grievances"));
}

export type SendFailure =
  | { key: "errorWait"; seconds: number }
  | { key: "errorSignIn" }
  | { key: "errorGeneric"; detail: string | null };

/** What to tell the person: the wait, the need to sign in, or the server's own sentence. */
export function sendFailure(error: unknown): SendFailure {
  if (error instanceof ApiError) {
    if (error.status === 429) return { key: "errorWait", seconds: error.retryAfter || 60 };
    if (error.status === 401) return { key: "errorSignIn" };
    return { key: "errorGeneric", detail: error.detail };
  }
  return { key: "errorGeneric", detail: null };
}
