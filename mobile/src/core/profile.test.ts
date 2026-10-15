import { EDUCATION_LEVELS, LIMITS, basicsFrom, profileBody, yearsFrom, type BasicsForm } from "./profile";

const form = (extra: Partial<BasicsForm> = {}): BasicsForm => ({
  fullName: "Asha Rao",
  headline: "Ward boy",
  state: "Maharashtra",
  district: "Pune",
  years: "3",
  education: "secondary",
  ...extra,
});

describe("the years of experience", () => {
  it("takes whole years up to the server's limit", () => {
    expect(yearsFrom("0")).toBe(0);
    expect(yearsFrom(" 7 ")).toBe(7);
    expect(yearsFrom("60")).toBe(60);
  });

  it("reads blank as not said, and refuses anything else", () => {
    expect(yearsFrom("")).toBeNull();
    expect(yearsFrom("   ")).toBeNull();
    for (const bad of ["61", "-1", "2.5", "two", "1e3", "999"]) expect(yearsFrom(bad)).toBeUndefined();
  });
});

describe("what is sent", () => {
  it("trims, and sends a cleared field as null so clearing it works", () => {
    expect(profileBody(form({ headline: "   ", district: "" }))).toMatchObject({
      headline: null,
      location_district: null,
      full_name: "Asha Rao",
    });
  });

  it("carries every field it edits, and only those", () => {
    expect(Object.keys(profileBody(form()) ?? {}).sort()).toEqual([
      "education_level",
      "full_name",
      "headline",
      "location_district",
      "location_state",
      "years_experience",
    ]);
  });

  it("sends nothing when the years are not a number the server would take", () => {
    expect(profileBody(form({ years: "abc" }))).toBeNull();
  });

  it("cuts a long entry to the server's limit rather than being refused for it", () => {
    const body = profileBody(form({ fullName: "x".repeat(500), headline: "y".repeat(500), state: "z".repeat(500) }));
    expect(body?.full_name).toHaveLength(LIMITS.fullName);
    expect(body?.headline).toHaveLength(LIMITS.headline);
    expect(body?.location_state).toHaveLength(LIMITS.place);
  });
});

describe("what the form starts from", () => {
  it("shows the profile as loaded, blanks for what was never said", () => {
    expect(basicsFrom({})).toEqual({ fullName: "", headline: "", state: "", district: "", years: "", education: null });
    expect(basicsFrom({ years_experience: 0, education_level: "iti" })).toMatchObject({ years: "0", education: "iti" });
  });

  it("ignores an education level the server does not know", () => {
    expect(basicsFrom({ education_level: "wizard" }).education).toBeNull();
  });
});

describe("the education levels", () => {
  it("are the eight the server accepts, in order of schooling", () => {
    expect(EDUCATION_LEVELS).toEqual([
      "none",
      "primary",
      "secondary",
      "higher_secondary",
      "iti",
      "diploma",
      "graduate",
      "postgraduate",
    ]);
  });
});
