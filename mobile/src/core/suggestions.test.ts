import { suggestionBadges, suggestionFacts, type Suggestion } from "./suggestions";

const t = (key: string, values?: Record<string, string | number>) =>
  values ? `${key}(${Object.entries(values).map(([k, v]) => `${k}=${v}`).join(",")})` : key;
const month = (m: number, style: string) => `${style}-m${m + 1}`;

const course = (extra: Partial<Suggestion> = {}): Suggestion =>
  ({
    slug: "c",
    title: "Phlebotomy",
    mode: "offline",
    language: "hi",
    duration_hours: 120,
    fee_inr: 12500,
    closes: [],
    closes_count: 1,
    gap_size: 3,
    covers_mandatory: 1,
    location_state: "Maharashtra",
    location_district: "Pune",
    starts_on: "2026-11-02",
    seats_left: 5,
    reach: "district",
    started: false,
    full: false,
    within_budget: null,
    attendable: true,
    ...extra,
  }) as Suggestion;

describe("the facts of a suggested course", () => {
  it("says how, where, when, what it costs, how long and how many places, in that order", () => {
    expect(suggestionFacts(course(), t, month)).toEqual([
      "mode.offline",
      "Pune, Maharashtra",
      "startsOn(date=2 short-m11 2026)",
      "fee(amount=12,500)",
      "hours(hours=120)",
      "seatsLeft(count=5)",
    ]);
  });

  it("names no place for an online course and says so for an in-person one with none stated", () => {
    expect(suggestionFacts(course({ mode: "online" }), t, month)).not.toContain("placeNotStated");
    expect(suggestionFacts(course({ mode: "online" }), t, month)[1]).toBe("startsOn(date=2 short-m11 2026)");
    expect(suggestionFacts(course({ location_district: null, location_state: null }), t, month)).toContain("placeNotStated");
  });

  it("reads a fee of zero or none as free", () => {
    expect(suggestionFacts(course({ fee_inr: 0 }), t, month)).toContain("free");
    expect(suggestionFacts(course({ fee_inr: null }), t, month)).toContain("free");
  });

  it("says started for a course already under way, and that no date was given when none was", () => {
    expect(suggestionFacts(course({ started: true }), t, month).join()).toContain("startedOn");
    expect(suggestionFacts(course({ starts_on: null }), t, month)).toContain("startNotStated");
  });

  it("does not list seats for a full course or one that did not say", () => {
    expect(suggestionFacts(course({ full: true, seats_left: 0 }), t, month).join()).not.toContain("seatsLeft");
    expect(suggestionFacts(course({ seats_left: null }), t, month).join()).not.toContain("seatsLeft");
  });
});

describe("the labels beside a suggested course", () => {
  it("shows how near it is, good for online, district and state and a warning for elsewhere", () => {
    expect(suggestionBadges(course({ reach: "online" }))).toEqual([{ key: "reach.online", tone: "success" }]);
    expect(suggestionBadges(course({ reach: "district" }))).toEqual([{ key: "reach.district", tone: "success" }]);
    expect(suggestionBadges(course({ reach: "state" }))).toEqual([{ key: "reach.state", tone: "success" }]);
    expect(suggestionBadges(course({ reach: "elsewhere" }))).toEqual([{ key: "reach.elsewhere", tone: "warning" }]);
  });

  it("labels, and never removes, a started, full or over-budget course", () => {
    const keys = suggestionBadges(course({ started: true, full: true, within_budget: false })).map((b) => b.key);
    expect(keys).toEqual(["reach.district", "started", "full", "overBudget"]);
  });

  it("makes no claim about a person when none is known", () => {
    const keys = suggestionBadges(course({ started: true, within_budget: false }), false).map((b) => b.key);
    expect(keys).toEqual(["started"]);
  });
});
