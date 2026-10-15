import {
  EDUCATION_LEVELS,
  EMPLOYMENT_TYPES,
  LIMITS,
  NOTICE_PERIODS,
  basicsFrom,
  preferencesBody,
  preferencesFrom,
  profileBody,
  rupees,
  yearsFrom,
  type BasicsForm,
  type PreferencesForm,
} from "./profile";

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


describe("what the person is looking for", () => {
  const prefs = (extra: Partial<PreferencesForm> = {}): PreferencesForm => ({
    salaryMin: "12000",
    salaryMax: "18000",
    notice: "within_15_days",
    employment: "full_time",
    relocate: true,
    alerts: true,
    ...extra,
  });

  it("offers every notice period and work type the server accepts", () => {
    expect(NOTICE_PERIODS).toHaveLength(4);
    expect(EMPLOYMENT_TYPES).toHaveLength(5);
  });

  it("reads rupees: blank is not said, grouping is ignored, rubbish is refused", () => {
    expect(rupees("")).toBeNull();
    expect(rupees("12,000")).toBe(12000);
    expect(rupees("0")).toBe(0);
    for (const bad of ["-1", "1.5", "abc", "1e5", "1234567890"]) expect(rupees(bad)).toBeUndefined();
  });

  it("builds the request, with a cleared field sent as null so clearing works", () => {
    expect(preferencesBody(prefs({ salaryMin: "", notice: null }))).toEqual({
      ok: true,
      body: {
        expected_salary_min_inr: null,
        expected_salary_max_inr: 18000,
        notice_period: null,
        preferred_employment_type: "full_time",
        willing_to_relocate: true,
        job_alerts_enabled: true,
      },
    });
  });

  it("refuses a maximum below the minimum, as the server does, and names which field", () => {
    expect(preferencesBody(prefs({ salaryMin: "20000", salaryMax: "10000" }))).toEqual({ ok: false, problem: "salaryOrder" });
    expect(preferencesBody(prefs({ salaryMin: "x" }))).toEqual({ ok: false, problem: "salaryMin" });
    expect(preferencesBody(prefs({ salaryMax: "-5" }))).toEqual({ ok: false, problem: "salaryMax" });
    expect(preferencesBody(prefs({ salaryMin: "5000", salaryMax: "5000" })).ok).toBe(true);
  });

  it("never carries the date of birth or the gender, which stay on the website", () => {
    const built = preferencesBody(prefs());
    expect(built.ok && Object.keys(built.body)).not.toEqual(expect.arrayContaining(["date_of_birth"]));
    expect(built.ok && Object.keys(built.body)).not.toEqual(expect.arrayContaining(["gender"]));
  });

  it("starts from the profile as loaded, and keeps alerts on unless it says off", () => {
    expect(preferencesFrom({ expected_salary_min_inr: 9000, notice_period: "immediate", job_alerts_enabled: false })).toMatchObject({
      salaryMin: "9000",
      notice: "immediate",
      alerts: false,
    });
    expect(preferencesFrom({}).alerts).toBe(true);
    expect(preferencesFrom({ notice_period: "soon" }).notice).toBeNull();
  });
});
