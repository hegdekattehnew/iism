import {
  experienceLabel,
  feeLabel,
  intakeLabel,
  lookalikeNames,
  mandatoryFirst,
  salaryLabel,
  seatsLabel,
  whereLabel,
} from "./labels";

// A translator that prints the key and its values, so a test sees which phrase was chosen.
const t = (key: string, values?: Record<string, string | number>) =>
  values ? `${key}(${Object.entries(values).map(([k, v]) => `${k}=${v}`).join(",")})` : key;
const month = (m: number) => ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m];

describe("experience", () => {
  it("says none when nothing is asked, a range when there is a ceiling, otherwise a floor", () => {
    expect(experienceLabel({ experience_min_years: 0 }, t)).toBe("experienceNone");
    expect(experienceLabel({ experience_min_years: 0, experience_max_years: null }, t)).toBe("experienceNone");
    expect(experienceLabel({ experience_min_years: 2, experience_max_years: 5 }, t)).toBe("experienceRange(min=2,max=5)");
    expect(experienceLabel({ experience_min_years: 3 }, t)).toBe("experience(min=3)");
  });

  it("treats a zero minimum with a ceiling as a range, not as none", () => {
    expect(experienceLabel({ experience_min_years: 0, experience_max_years: 2 }, t)).toBe("experienceRange(min=0,max=2)");
  });
});

describe("salary", () => {
  it("uses Indian grouping and falls back to undisclosed", () => {
    const terms = { experience_min_years: 0 };
    expect(salaryLabel({ ...terms, salary_min_inr: 240000, salary_max_inr: 360000 }, t)).toBe("salary(min=2,40,000,max=3,60,000)");
    expect(salaryLabel({ ...terms, salary_min_inr: 240000 }, t)).toBe("salaryFrom(min=2,40,000)");
    expect(salaryLabel({ ...terms, salary_max_inr: 360000 }, t)).toBe("salaryUndisclosed");
    expect(salaryLabel(terms, t)).toBe("salaryUndisclosed");
  });
});

describe("a course", () => {
  it("is free when the fee is zero or unstated", () => {
    expect(feeLabel({ fee_inr: 0 }, t)).toBe("feeFree");
    expect(feeLabel({ fee_inr: null }, t)).toBe("feeFree");
    expect(feeLabel({}, t)).toBe("feeFree");
    expect(feeLabel({ fee_inr: 12500 }, t)).toBe("fee(amount=12,500)");
  });

  it("has no place when it is online, never 'place not stated'", () => {
    expect(whereLabel({ mode: "online", location_state: "Kerala" }, t, true)).toBeNull();
  });

  it("names the district and state, and says so when an in-person course gives neither", () => {
    expect(whereLabel({ mode: "offline", location_district: "Pune", location_state: "Maharashtra" }, t)).toBe("Pune, Maharashtra");
    expect(whereLabel({ mode: "hybrid", location_state: "Kerala" }, t)).toBe("Kerala");
    expect(whereLabel({ mode: "offline" }, t)).toBeNull();
    expect(whereLabel({ mode: "offline" }, t, true)).toBe("placeNotStated");
  });

  it("starts or started, by what the server says, with the date in words", () => {
    expect(intakeLabel({ mode: "offline", starts_on: "2026-11-02", started: false }, t, month)).toBe("startsOn(date=2 Nov 2026)");
    expect(intakeLabel({ mode: "offline", starts_on: "2026-09-02", started: true }, t, month)).toBe("startedOn(date=2 Sep 2026)");
  });

  it("gives no intake line for no date or a date that is not one", () => {
    expect(intakeLabel({ mode: "offline" }, t, month)).toBeNull();
    expect(intakeLabel({ mode: "offline", starts_on: "soon" }, t, month)).toBeNull();
  });

  it("says full at zero seats left and nothing when the provider did not say", () => {
    expect(seatsLabel(0, t)).toBe("full");
    expect(seatsLabel(1, t)).toBe("seatsLeft(count=1)");
    expect(seatsLabel(null, t)).toBeNull();
    expect(seatsLabel(undefined, t)).toBeNull();
  });
});

describe("standards on a vacancy", () => {
  it("lists the mandatory ones first, then by importance", () => {
    const sorted = mandatoryFirst([
      { id: "a", is_mandatory: false, importance: 5 },
      { id: "b", is_mandatory: true, importance: 2 },
      { id: "c", is_mandatory: true, importance: 4 },
      { id: "d", is_mandatory: false, importance: 1 },
    ]);
    expect(sorted.map((s) => s.id)).toEqual(["c", "b", "a", "d"]);
  });

  it("does not reorder the list it was given", () => {
    const input = [
      { is_mandatory: false, importance: 1 },
      { is_mandatory: true, importance: 1 },
    ];
    mandatoryFirst(input);
    expect(input[0].is_mandatory).toBe(false);
  });

  it("flags names that appear twice, compared as a reader would", () => {
    const names = lookalikeNames([{ name: "Hand hygiene" }, { name: " hand hygiene " }, { name: "Triage" }]);
    expect([...names]).toEqual(["hand hygiene"]);
  });
});
