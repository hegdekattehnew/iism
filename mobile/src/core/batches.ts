/**
 * Batches on the phone (Sprint 102, ADR-103, BL-20.5): the plain functions over the typed client and
 * the rules a screen would otherwise carry. The web's `lib/batches.ts`, `RegisterBatch` and
 * `PublicBatchCard`, ported so the two say the same thing the same way.
 *
 * **Every query built from these is keyed under `"me"`** (`core/me-keys.ts`), never `"public"`: a
 * batch the person has registered for carries their own interest, and a public key is persisted to
 * the disk for offline reading. A visitor's list is asked for without a token and is not kept.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";
import type { Api } from "./api";
import { statusOf } from "./errors";
import { formatDate, formatInr } from "./format";
import { unwrap } from "./public";

export type PublicBatch = components["schemas"]["PublicBatchOut"];
export type BatchInterest = components["schemas"]["BatchInterestOut"];

export const BATCH_PAGE = 12;
export const BATCH_MODES = ["in_person", "hybrid", "online"] as const;
export type BatchMode = (typeof BATCH_MODES)[number];

export type BatchFilter = { course?: string; mode?: BatchMode | "" };

export async function listBatches(api: Api, filter: BatchFilter, offset = 0) {
  return unwrap(
    await api.GET("/batches", {
      params: {
        query: {
          limit: BATCH_PAGE,
          offset,
          ...(filter.course ? { course: filter.course } : {}),
          ...(filter.mode ? { mode: filter.mode } : {}),
        },
      },
    }),
  );
}

export async function getBatch(api: Api, id: string) {
  return unwrap(await api.GET("/batches/{batch_id}", { params: { path: { batch_id: id } } }));
}

export async function listBatchInterests(api: Api) {
  return unwrap(await api.GET("/me/batch-interests"));
}

export async function registerBatchInterest(api: Api, batchId: string, message: string) {
  const note = message.trim();
  return unwrap(
    await api.POST("/me/batch-interests", {
      body: { batch_id: batchId, message: note ? note : null },
    }),
  );
}

export async function withdrawBatchInterest(api: Api, interestId: string) {
  return unwrap(
    await api.POST("/me/batch-interests/{interest_id}/withdraw", {
      params: { path: { interest_id: interestId } },
    }),
  );
}

/** What the register control shows for a batch, one answer so the screens cannot disagree. */
export type RegisterState =
  | { kind: "mine"; interestId: string; status: string }
  | { kind: "full" }
  | { kind: "closed"; phase: "cancelled" | "running" | "finished" }
  | { kind: "open" };

export function registerState(batch: Pick<PublicBatch, "phase" | "my_interest">): RegisterState {
  const mine = batch.my_interest;
  if (mine) return { kind: "mine", interestId: mine.id, status: mine.status };
  if (batch.phase === "full") return { kind: "full" };
  if (batch.phase === "open") return { kind: "open" };
  // A draft is never public; anything that is neither open nor full is over, or never going to be.
  return {
    kind: "closed",
    phase: batch.phase === "cancelled" ? "cancelled" : batch.phase === "finished" ? "finished" : "running",
  };
}

/** A batch the learner can still take back: not withdrawn, not cancelled out from under them. */
export const canWithdrawBatch = (i: Pick<BatchInterest, "status" | "batch">): boolean =>
  i.status !== "withdrawn" && i.batch.phase !== "cancelled";

type Say = (key: string, values?: Record<string, string | number>) => string;

/**
 * Why registering or withdrawing failed, in the server's own words where it had any (a full batch,
 * a started one, a paused account and the daily cap each have their own sentence) and a fixed line
 * where it had none. 403 is "this is not a job seeker account".
 */
export function batchFailureText(error: unknown, t: Say): string {
  const status = statusOf(error);
  if (status === 403) return t("errorSeeker");
  const detail = (error as { detail?: string | null } | null)?.detail;
  if ((status === 404 || status === 409 || status === 429) && typeof detail === "string" && detail) {
    return detail;
  }
  return t("failed");
}

// ------------------------------------------------------------------- the card's words

type MonthName = (month: number, style: "short" | "long") => string;

export type BatchLines = {
  course: string;
  label: string | null;
  byLine: string;
  deliveredLine: string;
  dates: string;
  place: string | null;
  seats: string;
  fee: string | null;
  feeNote: string | null;
  mode: string;
  reach: { text: string; tone: "success" | "warning" } | null;
  schedule: string | null;
  verifiedSeller: boolean;
  verifiedOrganisation: boolean;
  verifiedCentre: boolean;
};

/**
 * Everything a batch card says, as text, from the batch and the catalogue's `publicBatches` words.
 * **Computes nothing the server did**: seats left, the phase and the reach are read, never derived.
 * A card never says "not verified" (an absent mark in a list reads as a charge); an unknown place
 * says nothing; a far batch is labelled, never hidden.
 */
export function batchLines(batch: PublicBatch, t: Say, monthName: MonthName): BatchLines {
  const date = (iso: string) => formatDate(iso, monthName, "short") ?? iso;
  const fee = batch.fee_effective;
  return {
    course: batch.course.title,
    label: batch.label ?? null,
    byLine: t("courseBy", { organisation: batch.course.provider.name }),
    deliveredLine: t("deliveredBy", { organisation: batch.organisation.name, centre: batch.centre.name }),
    dates: t("dates", { start: date(batch.starts_on), end: date(batch.ends_on) }),
    place: [batch.centre.location_district, batch.centre.location_state].filter(Boolean).join(", ") || null,
    seats:
      batch.phase === "full" ? t("full") : t("seatsLeft", { left: batch.seats_left, seats: batch.seats }),
    fee: fee == null ? null : fee === 0 ? t("feeFree") : t("fee", { amount: formatInr(fee) }),
    feeNote: batch.fee_is_override ? t("feeSetByCentre") : null,
    mode: t(`mode.${batch.mode}`),
    reach:
      batch.reach === "unknown"
        ? null
        : { text: t(`reach.${batch.reach}`), tone: batch.reach === "elsewhere" ? "warning" : "success" },
    schedule: batch.schedule ?? null,
    verifiedSeller: batch.course.provider.is_verified === true,
    verifiedOrganisation: batch.organisation.is_verified === true,
    verifiedCentre: batch.centre.is_verified === true,
  };
}

// ------------------------------------------------------------ when to expect a reply

/** Three days: the web's `lib/interest-reply`. **An ask, never a promise** (ADR-100). */
export const REPLY_WITHIN_DAYS = 3;

/** The moment a reply is asked for by, as an instant the date formatter reads. */
export function replyByInstant(registeredAt: string): string | null {
  const start = Date.parse(registeredAt);
  if (!Number.isFinite(start)) return null;
  return new Date(start + REPLY_WITHIN_DAYS * 24 * 60 * 60 * 1000).toISOString();
}

/** Still waiting for the centre: registered, not answered, and the batch is not cancelled. */
export const awaitingReply = (i: Pick<BatchInterest, "status" | "batch">): boolean =>
  i.status === "registered" && i.batch.phase !== "cancelled";
