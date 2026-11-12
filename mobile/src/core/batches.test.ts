import {
  awaitingReply,
  batchFailureText,
  batchLines,
  canWithdrawBatch,
  getBatch,
  listBatches,
  registerBatchInterest,
  registerState,
  replyByInstant,
  withdrawBatchInterest,
  type PublicBatch,
} from "./batches";
import { ApiError } from "./errors";

/** A translator that shows its key and values, so which words were chosen is visible. */
const t = (key: string, values?: Record<string, string | number>) =>
  values ? `${key}(${Object.entries(values).map(([k, v]) => `${k}=${v}`).join(",")})` : key;
const monthName = (m: number, style: "short" | "long") => `${style}${m}`;

const batch = (extra: Record<string, unknown> = {}) =>
  ({
    id: "b1",
    course: { slug: "welding", title: "Welding", provider: { name: "Seller", is_verified: true } },
    centre: { name: "Hadapsar", location_district: "Pune", location_state: "Maharashtra", is_verified: false },
    organisation: { name: "Partner", is_verified: false },
    label: null,
    starts_on: "2026-11-09",
    ends_on: "2026-12-09",
    seats: 20,
    seats_left: 12,
    mode: "in_person",
    schedule: null,
    fee_effective: 4000,
    fee_is_override: false,
    phase: "open",
    reach: "district",
    my_interest: null,
    ...extra,
  }) as unknown as PublicBatch;

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });
const apiOf = () => ({ GET: jest.fn().mockResolvedValue(ok({})), POST: jest.fn().mockResolvedValue(ok({})) });

describe("asking the API for batches", () => {
  it("sends a page of twelve, the course and the way it is taught, and nothing for a blank filter", async () => {
    const api = apiOf();
    await listBatches(api as never, { course: "welding", mode: "online" }, 24);
    expect(api.GET).toHaveBeenCalledWith("/batches", {
      params: { query: { limit: 12, offset: 24, course: "welding", mode: "online" } },
    });
    await listBatches(api as never, { course: "", mode: "" });
    expect(api.GET.mock.calls[1][1].params.query).toEqual({ limit: 12, offset: 0 });
  });

  it("asks for one batch by id", async () => {
    const api = apiOf();
    await getBatch(api as never, "b9");
    expect(api.GET).toHaveBeenCalledWith("/batches/{batch_id}", { params: { path: { batch_id: "b9" } } });
  });

  it("sends the note trimmed, and null for a blank one", async () => {
    const api = apiOf();
    await registerBatchInterest(api as never, "b1", "  Evenings only ");
    expect(api.POST.mock.calls[0]).toEqual(["/me/batch-interests", { body: { batch_id: "b1", message: "Evenings only" } }]);
    await registerBatchInterest(api as never, "b1", "   ");
    expect(api.POST.mock.calls[1][1].body.message).toBeNull();
  });

  it("withdraws by the interest's own id", async () => {
    const api = apiOf();
    await withdrawBatchInterest(api as never, "i7");
    expect(api.POST).toHaveBeenCalledWith("/me/batch-interests/{interest_id}/withdraw", {
      params: { path: { interest_id: "i7" } },
    });
  });

  it("keeps the status and the server's sentence when it refuses", async () => {
    const api = apiOf();
    api.POST.mockResolvedValue({ data: undefined, error: { detail: "This batch is full" }, response: { status: 409 } });
    await expect(registerBatchInterest(api as never, "b1", "")).rejects.toMatchObject({
      status: 409,
      detail: "This batch is full",
    });
  });
});

describe("what the register control shows", () => {
  it("is one answer per batch", () => {
    expect(registerState(batch())).toEqual({ kind: "open" });
    expect(registerState(batch({ phase: "full" }))).toEqual({ kind: "full" });
    expect(registerState(batch({ phase: "cancelled" }))).toEqual({ kind: "closed", phase: "cancelled" });
    expect(registerState(batch({ phase: "running" }))).toEqual({ kind: "closed", phase: "running" });
    expect(registerState(batch({ phase: "finished" }))).toEqual({ kind: "closed", phase: "finished" });
  });

  it("puts the person's own interest first, whatever the phase", () => {
    const mine = { id: "i1", status: "enrolled" };
    for (const phase of ["open", "full", "running", "cancelled"]) {
      expect(registerState(batch({ phase, my_interest: mine }))).toEqual({
        kind: "mine",
        interestId: "i1",
        status: "enrolled",
      });
    }
  });
});

describe("what a learner may take back", () => {
  it("not a withdrawn interest, and not a batch that was cancelled from under them", () => {
    const i = (status: string, phase: string) => ({ status, batch: batch({ phase }) }) as never;
    expect(canWithdrawBatch(i("registered", "open"))).toBe(true);
    expect(canWithdrawBatch(i("enrolled", "running"))).toBe(true);
    expect(canWithdrawBatch(i("withdrawn", "open"))).toBe(false);
    expect(canWithdrawBatch(i("registered", "cancelled"))).toBe(false);
  });

  it("is waiting for a reply only while registered and not cancelled", () => {
    const i = (status: string, phase: string) => ({ status, batch: batch({ phase }) }) as never;
    expect(awaitingReply(i("registered", "open"))).toBe(true);
    expect(awaitingReply(i("contacted", "open"))).toBe(false);
    expect(awaitingReply(i("registered", "cancelled"))).toBe(false);
  });

  it("is asked to reply within three days, as an instant", () => {
    expect(replyByInstant("2026-10-20T09:00:00Z")).toBe("2026-10-23T09:00:00.000Z");
    expect(replyByInstant("not a date")).toBeNull();
  });
});

describe("why it failed, in the server's own words", () => {
  it("keeps the sentence for a refusal the server explained", () => {
    for (const status of [404, 409, 429]) {
      expect(batchFailureText(new ApiError(status, "This batch is full"), t)).toBe("This batch is full");
    }
  });

  it("says a non-seeker account is not one, and a bare failure is the fixed line", () => {
    expect(batchFailureText(new ApiError(403, "Forbidden"), t)).toBe("errorSeeker");
    expect(batchFailureText(new ApiError(500, "boom"), t)).toBe("failed");
    expect(batchFailureText(new ApiError(409, null), t)).toBe("failed");
    expect(batchFailureText(new Error("network"), t)).toBe("failed");
  });
});

describe("a batch card's words", () => {
  it("names who sells it and who runs it, with dates, place, seats and fee", () => {
    const l = batchLines(batch(), t, monthName);
    expect(l.byLine).toBe("courseBy(organisation=Seller)");
    expect(l.deliveredLine).toBe("deliveredBy(organisation=Partner,centre=Hadapsar)");
    expect(l.dates).toBe("dates(start=9 short10 2026,end=9 short11 2026)");
    expect(l.place).toBe("Pune, Maharashtra");
    expect(l.seats).toBe("seatsLeft(left=12,seats=20)");
    expect(l.fee).toBe("fee(amount=4,000)");
    expect(l.mode).toBe("mode.in_person");
  });

  it("says a full batch is full and draws no count", () => {
    expect(batchLines(batch({ phase: "full", seats_left: 0 }), t, monthName).seats).toBe("full");
  });

  it("calls a zero fee free, says nothing of an unstated one, and names a centre's own fee", () => {
    expect(batchLines(batch({ fee_effective: 0 }), t, monthName).fee).toBe("feeFree");
    expect(batchLines(batch({ fee_effective: null }), t, monthName).fee).toBeNull();
    expect(batchLines(batch({ fee_is_override: true }), t, monthName).feeNote).toBe("feeSetByCentre");
    expect(batchLines(batch(), t, monthName).feeNote).toBeNull();
  });

  it("says nothing about an unknown place, and warns about a far one without hiding it", () => {
    expect(batchLines(batch({ reach: "unknown" }), t, monthName).reach).toBeNull();
    expect(batchLines(batch({ reach: "elsewhere" }), t, monthName).reach).toEqual({
      text: "reach.elsewhere",
      tone: "warning",
    });
    expect(batchLines(batch({ reach: "online" }), t, monthName).reach?.tone).toBe("success");
  });

  it("reads the marks as facts, and has no word for 'not verified'", () => {
    const l = batchLines(batch(), t, monthName);
    expect(l.verifiedSeller).toBe(true);
    expect(l.verifiedOrganisation).toBe(false);
    expect(l.verifiedCentre).toBe(false);
    expect(JSON.stringify(l)).not.toMatch(/not verified|unverified/i);
  });

  it("leaves out a place the centre has not stated", () => {
    const l = batchLines(
      batch({ centre: { name: "H", location_district: null, location_state: null, is_verified: false } }),
      t,
      monthName,
    );
    expect(l.place).toBeNull();
  });
});
