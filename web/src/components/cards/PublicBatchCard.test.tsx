import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BATCH_INTEREST_LOOK } from "@/components/cards/batch-interest-look";
import { PublicBatchCard } from "@/components/cards/PublicBatchCard";
import { BatchInterestCard } from "@/components/cards/BatchInterestCard";
import { batchInterest, publicBatch } from "@/test/batch-fixtures";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

const batch = publicBatch;

/** Sprint 100, BL-20.2: a batch as a learner sees it, nearest and soonest. */
describe("PublicBatchCard", () => {
  it("makes the course link a 44 px target (a title link is a control, not a sentence)", () => {
    renderUi(<PublicBatchCard batch={batch()} />);
    expect(screen.getByRole("link", { name: "Welding basics" }).className).toContain("min-h-11");
  });

  it("names who sells the course and who runs it, linking the course", () => {
    renderUi(<PublicBatchCard batch={batch()} />);
    expect(screen.getByRole("link", { name: "Welding basics" }).getAttribute("href")).toBe("/courses/welding");
    expect(screen.getByText("Course by Seller Academy")).toBeTruthy();
    expect(screen.getByText("Delivered by Partner Skills at Hadapsar Centre")).toBeTruthy();
  });

  it("marks the seller and the centre where earned and never says 'not verified'", () => {
    renderUi(<PublicBatchCard batch={batch()} />);
    expect(screen.getAllByText("Reviewed by our team")).toHaveLength(1); // the seller only
    expect(screen.getByText("Address checked")).toBeTruthy();
    expect(screen.queryByText(/not verified|not yet/i)).toBeNull();
  });

  it("marks each organisation only for what is true of it", () => {
    const a = renderUi(
      <PublicBatchCard
        batch={batch({
          course: { ...batch().course, provider: { slug: "s", name: "Seller Academy", is_verified: false } },
          centre: { ...batch().centre, is_verified: false },
          organisation: { slug: "p", name: "Partner Skills", is_verified: false },
        })}
      />,
    );
    expect(screen.queryByText("Reviewed by our team")).toBeNull();
    expect(screen.queryByText("Address checked")).toBeNull();
    a.unmount();
    renderUi(
      <PublicBatchCard
        batch={batch({
          course: { ...batch().course, provider: { slug: "s", name: "Seller Academy", is_verified: false } },
          organisation: { slug: "p", name: "Partner Skills", is_verified: true },
        })}
      />,
    );
    // The partner's mark is the partner's: one, beside who delivers it, and none beside the seller.
    expect(screen.getAllByText("Reviewed by our team")).toHaveLength(1);
    expect(
      screen.getByText("Reviewed by our team").parentElement?.textContent ?? "",
    ).toContain("Delivered by Partner Skills");
  });

  it("shows the calendar date the server said, in any zone the browser is in", () => {
    // A date is parsed and formatted as UTC: as local midnight it slips a day east of the line.
    const was = process.env.TZ;
    process.env.TZ = "Pacific/Kiritimati";
    try {
      renderUi(<PublicBatchCard batch={batch()} />);
      expect(screen.getByText("Nov 9, 2026 to Dec 9, 2026")).toBeTruthy();
    } finally {
      if (was === undefined) delete process.env.TZ;
      else process.env.TZ = was;
    }
  });

  it.each([
    ["online", "Online"],
    ["district", "In your district"],
    ["state", "In your state"],
    ["elsewhere", "Outside your state"],
  ] as const)("says how near it is: %s", (reach, words) => {
    renderUi(<PublicBatchCard batch={batch({ reach })} />);
    expect(screen.getByText(words, { selector: "span" })).toBeTruthy();
  });

  it("says nothing about distance when the place is not known", () => {
    renderUi(<PublicBatchCard batch={batch({ reach: "unknown" })} />);
    expect(screen.queryByText(/your district|your state|Outside|Place not known/)).toBeNull();
  });

  it("shows the dates in the learner's calendar, the place, seats left, the fee and the mode", () => {
    renderUi(<PublicBatchCard batch={batch({ schedule: "Mon to Fri, 9 to 1" })} />);
    expect(screen.getByText("Nov 9, 2026 to Dec 9, 2026")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("12 of 20 seats left")).toBeTruthy();
    expect(screen.getByText("₹4,000")).toBeTruthy();
    expect(screen.getByText("In person")).toBeTruthy();
    expect(screen.getByText("Mon to Fri, 9 to 1")).toBeTruthy();
  });

  it("labels a full batch as full and draws no count of seats left for it", () => {
    renderUi(<PublicBatchCard batch={batch({ phase: "full", seats_left: 0 })} />);
    expect(screen.getByText("Full")).toBeTruthy();
    expect(screen.queryByText(/seats left/)).toBeNull();
  });

  it("says when the centre set the fee, calls nothing free that is not, and omits an unstated fee", () => {
    const a = renderUi(<PublicBatchCard batch={batch({ fee_effective: 3500, fee_is_override: true })} />);
    expect(screen.getByText("Fee set by the centre")).toBeTruthy();
    a.unmount();
    const b = renderUi(<PublicBatchCard batch={batch({ fee_effective: 0 })} />);
    expect(screen.getByText("Free")).toBeTruthy();
    b.unmount();
    renderUi(<PublicBatchCard batch={batch({ fee_effective: null })} />);
    expect(screen.queryByText(/₹/)).toBeNull();
  });

  it("carries no word about anybody else: no count of the interested, no contact", () => {
    const { container } = renderUi(<PublicBatchCard batch={batch()} />);
    expect(container.textContent ?? "").not.toMatch(/interested|enrolled|phone|email/i);
  });

  it("renders what the list passes as its footer, and is not itself a link", () => {
    renderUi(<PublicBatchCard batch={batch()} footer={<button>Register</button>} />);
    expect(screen.getByRole("button", { name: "Register" })).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});

const interest = batchInterest;

describe("BatchInterestCard", () => {
  it.each([
    ["registered", "Registered"],
    ["contacted", "They got in touch"],
    ["enrolled", "Enrolled"],
    ["attended", "Attended"],
    ["withdrawn", "Withdrawn"],
  ] as const)("draws %s as the word %s with a shape", (status, word) => {
    renderUi(<BatchInterestCard interest={interest({ status })} />);
    expect(screen.getByText(word, { selector: "span" }).querySelector("svg")).toBeTruthy();
  });

  it("makes the course link a 44 px target", () => {
    renderUi(<BatchInterestCard interest={interest()} />);
    expect(screen.getByRole("link", { name: "Welding basics" }).className).toContain("min-h-11");
  });

  it("gives the date a reply is expected by, as an ask, while nobody has answered", () => {
    renderUi(<BatchInterestCard interest={interest()} />);
    expect(screen.getByText("Reply expected by Oct 23, 2026")).toBeTruthy();
    expect(screen.getByText("Centres are asked to reply within 3 days.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Not heard back? Tell us" }).getAttribute("href")).toBe("/contact");
  });

  it("stops saying it once the centre has answered", () => {
    renderUi(<BatchInterestCard interest={interest({ status: "contacted" })} />);
    expect(screen.queryByText(/Reply expected/)).toBeNull();
  });

  it.each([
    ["by_organisation", "The centre cancelled this batch."],
    ["arrangement_ended", "The centre can no longer offer this course, so this batch was cancelled."],
    ["course_unavailable", "The course is no longer available, so this batch was cancelled."],
    ["centre_closed", "The centre closed, so this batch was cancelled."],
  ] as const)("says why a cancelled batch was cancelled: %s", (reason, sentence) => {
    renderUi(
      <BatchInterestCard
        interest={interest({ batch: batch({ phase: "cancelled", cancel_reason: reason }) })}
      />,
    );
    expect(screen.getByText(sentence)).toBeTruthy();
    expect(screen.queryByText(/Reply expected/)).toBeNull();
  });
});

describe("BATCH_INTEREST_LOOK", () => {
  it("gives no two states the same shape", () => {
    const states = Object.keys(BATCH_INTEREST_LOOK) as (keyof typeof BATCH_INTEREST_LOOK)[];
    expect(states.sort()).toEqual(["attended", "contacted", "enrolled", "registered", "withdrawn"]);
    const drawn = states.map((s) => {
      const Icon = BATCH_INTEREST_LOOK[s].icon;
      const { container, unmount } = renderUi(<Icon />);
      const html = container.innerHTML;
      unmount();
      return html;
    });
    expect(new Set(drawn).size).toBe(states.length);
  });
});
