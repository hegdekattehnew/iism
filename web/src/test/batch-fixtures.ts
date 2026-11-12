import type { BatchInterest, BatchLearner, PublicBatch } from "@/lib/batches";

/** A public batch as the server sends it; a test names only what it varies (Sprint 100). */
export const publicBatch = (over: Record<string, unknown> = {}): PublicBatch =>
  ({
    id: "b1",
    course: {
      slug: "welding",
      title: "Welding basics",
      fee_inr: 4000,
      available: true,
      own: false,
      provider: { slug: "seller", name: "Seller Academy", is_verified: true },
    },
    centre: {
      slug: "hadapsar",
      name: "Hadapsar Centre",
      location_district: "Pune",
      location_state: "Maharashtra",
      is_verified: true,
    },
    organisation: { slug: "partner", name: "Partner Skills", is_verified: false },
    label: "Morning batch",
    starts_on: "2026-11-09",
    ends_on: "2026-12-09",
    seats: 20,
    seats_left: 12,
    mode: "in_person",
    schedule: null,
    fee_effective: 4000,
    fee_is_override: false,
    phase: "open",
    cancel_reason: null,
    reach: "district",
    my_interest: null,
    ...over,
  }) as unknown as PublicBatch;

export const batchInterest = (over: Record<string, unknown> = {}): BatchInterest =>
  ({
    id: "i1",
    batch: publicBatch(),
    status: "registered",
    message: null,
    registered_at: "2026-10-20T09:00:00Z",
    updated_at: "2026-10-20T09:00:00Z",
    ...over,
  }) as unknown as BatchInterest;

export const batchLearner = (over: Record<string, unknown> = {}): BatchLearner =>
  ({
    interest_id: "i1",
    status: "registered",
    registered_at: "2026-10-20T09:00:00Z",
    message: null,
    location_district: "Pune",
    location_state: "Maharashtra",
    contact: { full_name: "Asha Rao", phone: "+919800000001", email: "asha@example.com" },
    ...over,
  }) as unknown as BatchLearner;
