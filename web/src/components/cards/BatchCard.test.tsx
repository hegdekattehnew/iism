import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BATCH_LOOK } from "@/components/cards/batch-look";
import { BatchCard } from "@/components/cards/BatchCard";
import { BATCH_PHASES, type Batch } from "@/lib/batches";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

const batch = (over: Record<string, unknown> = {}): Batch =>
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
    organisation: { slug: "partner", name: "Partner Skills", is_verified: true },
    label: "Morning batch",
    starts_on: "2026-11-09",
    ends_on: "2026-12-09",
    seats: 20,
    enrolled: 5,
    seats_left: 15,
    interested: 7,
    mode: "in_person",
    schedule: "Mon to Fri, 9 to 1",
    fee_inr: null,
    fee_effective: 4000,
    fee_is_override: false,
    status: "published",
    phase: "open",
    cancel_reason: null,
    ...over,
  }) as unknown as Batch;

/** Sprint 98, ADR-103: one run of a course at a centre, named for both organisations. */
describe("BatchCard", () => {
  it("names the course's seller and the organisation and centre that deliver it", () => {
    renderUi(<BatchCard batch={batch()} />);
    expect(screen.getByRole("heading", { name: "Welding basics" })).toBeTruthy();
    expect(screen.getByText("Course by Seller Academy")).toBeTruthy();
    expect(screen.getByText("Delivered by Partner Skills at Hadapsar Centre")).toBeTruthy();
  });

  it("says 'Your own course' instead of naming the organisation twice", () => {
    renderUi(<BatchCard batch={batch({ course: { ...batch().course, own: true } })} />);
    expect(screen.getByText("Your own course")).toBeTruthy();
    expect(screen.queryByText(/Course by/)).toBeNull();
  });

  it("shows each organisation's own mark, and the centre's separately", () => {
    renderUi(<BatchCard batch={batch()} />);
    // The seller, the deliverer and the centre: two "Reviewed" marks and one "Address checked".
    expect(screen.getAllByText("Reviewed by our team")).toHaveLength(2);
    expect(screen.getByText("Address checked")).toBeTruthy();
  });

  it("keeps the centre's mark apart from its organisation's", () => {
    // Only the organisation is reviewed: "Address checked" must not appear for it.
    const a = renderUi(
      <BatchCard
        batch={batch({
          course: { ...batch().course, provider: { slug: "s", name: "Seller Academy", is_verified: false } },
          centre: { ...batch().centre, is_verified: false },
        })}
      />,
    );
    expect(screen.getAllByText("Reviewed by our team")).toHaveLength(1);
    expect(screen.queryByText("Address checked")).toBeNull();
    a.unmount();
    // Only the centre's address is checked: its organisation is not "reviewed" because of it.
    renderUi(
      <BatchCard
        batch={batch({
          course: { ...batch().course, provider: { slug: "s", name: "Seller Academy", is_verified: false } },
          organisation: { slug: "p", name: "Partner Skills", is_verified: false },
        })}
      />,
    );
    expect(screen.getByText("Address checked")).toBeTruthy();
    expect(screen.queryByText("Reviewed by our team")).toBeNull();
  });

  it("never says 'not verified' of anybody, and draws no mark that is not earned", () => {
    renderUi(
      <BatchCard
        batch={batch({
          course: { ...batch().course, provider: { slug: "s", name: "Seller Academy", is_verified: false } },
          centre: { ...batch().centre, is_verified: false },
          organisation: { slug: "p", name: "Partner Skills", is_verified: false },
        })}
      />,
    );
    expect(screen.queryByText("Reviewed by our team")).toBeNull();
    expect(screen.queryByText("Address checked")).toBeNull();
    expect(screen.queryByText(/not verified|not yet/i)).toBeNull();
  });

  it("shows the dates in the learner's calendar, the place, the seats left and the fee", () => {
    renderUi(<BatchCard batch={batch()} />);
    expect(screen.getByText("Nov 9, 2026 to Dec 9, 2026")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("15 of 20 seats left")).toBeTruthy();
    expect(screen.getByText("₹4,000")).toBeTruthy();
    expect(screen.getByText("In person")).toBeTruthy();
    expect(screen.getByText("Mon to Fri, 9 to 1")).toBeTruthy();
  });

  it("says when the centre set the fee, and that a fee of nothing is free", () => {
    const a = renderUi(<BatchCard batch={batch({ fee_effective: 3500, fee_is_override: true })} />);
    expect(screen.getByText("₹3,500")).toBeTruthy();
    expect(screen.getByText("Fee set by the centre")).toBeTruthy();
    a.unmount();
    renderUi(<BatchCard batch={batch({ fee_effective: 0 })} />);
    expect(screen.getByText("Free")).toBeTruthy();
    expect(screen.queryByText("Fee set by the centre")).toBeNull();
  });

  it("draws no fee when neither the batch nor the course states one", () => {
    renderUi(<BatchCard batch={batch({ fee_effective: null })} />);
    expect(screen.queryByText(/₹/)).toBeNull();
  });

  it.each([
    ["draft", "Draft"],
    ["open", "Open"],
    ["full", "Full"],
    ["running", "Running"],
    ["finished", "Finished"],
    ["cancelled", "Cancelled"],
  ] as const)("draws %s as the word %s with a shape", (phase, word) => {
    const extra = phase === "cancelled" ? { status: "cancelled", cancel_reason: "by_organisation" } : {};
    renderUi(<BatchCard batch={batch({ phase, ...extra })} />);
    expect(screen.getByText(word, { selector: "span" }).querySelector("svg")).toBeTruthy();
  });

  it("counts the seats of a draft or a cancelled batch, not the seats left", () => {
    const a = renderUi(<BatchCard batch={batch({ phase: "draft", status: "draft" })} />);
    expect(screen.getByText("20 seats")).toBeTruthy();
    expect(screen.queryByText(/seats left/)).toBeNull();
    a.unmount();
    renderUi(<BatchCard batch={batch({ phase: "cancelled", status: "cancelled", cancel_reason: "centre_closed" })} />);
    expect(screen.getByText("20 seats")).toBeTruthy();
  });

  it.each([
    ["by_organisation", "Cancelled by your organisation."],
    ["arrangement_ended", "Cancelled because the arrangement to deliver this course ended."],
    ["course_unavailable", "Cancelled because the course is no longer available."],
    ["centre_closed", "Cancelled because the centre closed."],
  ] as const)("says why a batch was cancelled: %s", (reason, sentence) => {
    renderUi(<BatchCard batch={batch({ phase: "cancelled", status: "cancelled", cancel_reason: reason })} />);
    expect(screen.getByText(sentence)).toBeTruthy();
  });

  it("warns, for a batch that is not over, when its course is not published", () => {
    const a = renderUi(<BatchCard batch={batch({ course: { ...batch().course, available: false } })} />);
    expect(screen.getByText(/this course is not published/i)).toBeTruthy();
    a.unmount();
    renderUi(
      <BatchCard batch={batch({ phase: "finished", course: { ...batch().course, available: false } })} />,
    );
    expect(screen.queryByText(/this course is not published/i)).toBeNull();
  });

  it("renders what the list passes as its footer", () => {
    renderUi(<BatchCard batch={batch()} footer={<button>Publish</button>} />);
    expect(screen.getByRole("button", { name: "Publish" })).toBeTruthy();
  });

  it("is not a link or a button itself (it holds buttons)", () => {
    renderUi(<BatchCard batch={batch()} footer={<button>Publish</button>} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});

describe("BATCH_LOOK", () => {
  it("has a look for every phase the server can say", () => {
    expect(Object.keys(BATCH_LOOK).sort()).toEqual([...BATCH_PHASES].sort());
  });

  it("gives no two phases the same shape", () => {
    // A set of tone + shape would pass if two phases shared both; compare the drawn markup.
    const drawn = BATCH_PHASES.map((p) => {
      const Icon = BATCH_LOOK[p].icon;
      const { container, unmount } = renderUi(<Icon />);
      const html = container.innerHTML;
      unmount();
      return html;
    });
    expect(new Set(drawn).size).toBe(BATCH_PHASES.length);
  });

  it("is neutral for a draft and a finished batch, and warns only for a cancelled one", () => {
    expect(BATCH_LOOK.draft.tone).toBe("neutral");
    expect(BATCH_LOOK.finished.tone).toBe("neutral");
    expect(BATCH_LOOK.cancelled.tone).toBe("warn");
    expect(BATCH_PHASES.filter((p) => BATCH_LOOK[p].tone === "warn")).toEqual(["cancelled"]);
  });
});
