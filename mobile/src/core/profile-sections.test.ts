import {
  COLLECTIONS,
  FIELDS,
  blankForm,
  bodyFromForm,
  formFromEntry,
  isCollection,
  isVisible,
  monthKey,
  problemFor,
  setFlag,
  summaryOf,
  yearKey,
  type Collection,
  type Entry,
  type Form,
} from "./profile-sections";

const ok = (collection: Collection, form: Form) => {
  const built = bodyFromForm(collection, form);
  if (!built.ok) throw new Error(`expected ok, got ${JSON.stringify(built.problems)}`);
  return built.body;
};
const bad = (collection: Collection, form: Form) => {
  const built = bodyFromForm(collection, form);
  if (built.ok) throw new Error("expected problems");
  return built.problems;
};
const months = (m: number) => ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m];

const experience = (over: Form = {}): Form => ({
  ...blankForm("experiences"),
  employer_name: "Apollo Care",
  role_title: "Ward attendant",
  [monthKey("started_on")]: "4",
  [yearKey("started_on")]: "2019",
  ...over,
});

describe("the table", () => {
  it("covers all six sections the server routes", () => {
    expect([...COLLECTIONS].sort()).toEqual(
      ["certifications", "educations", "experiences", "languages", "preferred_locations", "preferred_roles"].sort(),
    );
    for (const c of COLLECTIONS) expect(FIELDS[c].length).toBeGreaterThan(0);
  });

  it("only a known section is a section (a typo or a hostile link reaches nothing)", () => {
    expect(isCollection("experiences")).toBe(true);
    expect(isCollection("skills")).toBe(false);
    expect(isCollection("../etc")).toBe(false);
    expect(isCollection(undefined)).toBe(false);
  });
});

describe("work history", () => {
  it("builds the request the server takes, dates as the first of the month", () => {
    expect(ok("experiences", experience())).toEqual({
      employer_name: "Apollo Care",
      role_title: "Ward attendant",
      location: null,
      started_on: "2019-04-01",
      ended_on: null,
      is_current: false,
      description: null,
    });
  });

  it("asks for the employer, the role and a start", () => {
    const problems = bad("experiences", { ...blankForm("experiences") });
    expect(problems.map((p) => p.field).sort()).toEqual(["employer_name", "role_title", "started_on"]);
    expect(problems.every((p) => p.code === "required")).toBe(true);
  });

  it("refuses an end before the start, in the server's terms", () => {
    const problems = bad("experiences", experience({ [monthKey("ended_on")]: "3", [yearKey("ended_on")]: "2019" }));
    expect(problemFor(problems, "ended_on")).toBe("order");
  });

  it("accepts an end in the same month as the start", () => {
    const body = ok("experiences", experience({ [monthKey("ended_on")]: "4", [yearKey("ended_on")]: "2019" }));
    expect(body.ended_on).toBe("2019-04-01");
  });

  it("a job the person still holds has no end date, whatever was typed", () => {
    const body = ok(
      "experiences",
      experience({ is_current: true, [monthKey("ended_on")]: "1", [yearKey("ended_on")]: "2018" }),
    );
    expect(body.ended_on).toBeNull();
    expect(body.is_current).toBe(true);
  });

  it("setting 'I work here' clears a typed end, as the server does, and hides the field", () => {
    const typed = experience({ [monthKey("ended_on")]: "6", [yearKey("ended_on")]: "2022" });
    const next = setFlag("experiences", typed, "is_current", true);
    expect(next[monthKey("ended_on")]).toBe("");
    expect(next[yearKey("ended_on")]).toBe("");
    const end = FIELDS.experiences.find((f) => f.key === "ended_on")!;
    expect(isVisible(end, next)).toBe(false);
    expect(isVisible(end, setFlag("experiences", next, "is_current", false))).toBe(true);
  });

  it.each([
    ["0", "2019"],
    ["13", "2019"],
    ["x", "2019"],
    ["4", "1949"],
    ["4", "2101"],
    ["4", ""],
    ["", "2019"],
    ["4.5", "2019"],
  ])("refuses the date month %s year %s", (month, year) => {
    const problems = bad("experiences", experience({ [monthKey("started_on")]: month, [yearKey("started_on")]: year }));
    expect(problemFor(problems, "started_on")).not.toBeNull();
  });

  it("holds the server's length limits", () => {
    expect(problemFor(bad("experiences", experience({ employer_name: "x".repeat(121) })), "employer_name")).toBe("long");
    expect(problemFor(bad("experiences", experience({ description: "x".repeat(1001) })), "description")).toBe("long");
    expect(ok("experiences", experience({ description: "x".repeat(1000) })).description).toHaveLength(1000);
  });

  it("trims, and a blank optional field is null (cleared), never an empty string", () => {
    const body = ok("experiences", experience({ employer_name: "  Apollo Care  ", location: "   " }));
    expect(body.employer_name).toBe("Apollo Care");
    expect(body.location).toBeNull();
  });
});

describe("editing keeps what the phone does not touch", () => {
  const entry: Entry = {
    id: "e1",
    employer_name: "Apollo Care",
    role_title: "Ward attendant",
    location: "Nagpur",
    started_on: "2019-04-15",
    ended_on: "2021-09-30",
    is_current: false,
    description: "Night shifts",
  };

  it("an unchanged month and year send back the exact date the website recorded", () => {
    const form = formFromEntry("experiences", entry);
    expect(form[monthKey("started_on")]).toBe("4");
    const body = ok("experiences", { ...form, description: "Day shifts" });
    expect(body.started_on).toBe("2019-04-15");
    expect(body.ended_on).toBe("2021-09-30");
    expect(body.description).toBe("Day shifts");
  });

  it("a changed month is sent as the first of that month", () => {
    const form = { ...formFromEntry("experiences", entry), [monthKey("started_on")]: "5" };
    expect(ok("experiences", form).started_on).toBe("2019-05-01");
  });

  it("a certificate's NSQF level, which the phone never shows, travels back unchanged", () => {
    const cert: Entry = { id: "c1", name: "First aid", issuing_body: "Red Cross", credential_id: null, issued_on: "2020-01-10", expires_on: null, nsqf_level: 4.5, skill: null };
    const form = formFromEntry("certifications", cert);
    expect(ok("certifications", form).nsqf_level).toBe(4.5);
    const none = formFromEntry("certifications", { ...cert, nsqf_level: null });
    expect(ok("certifications", none).nsqf_level).toBeNull();
  });

  it("never sends a skill link, so the server leaves the one the website made alone", () => {
    const body = ok("certifications", formFromEntry("certifications", { id: "c1", name: "First aid", skill: { slug: "first-aid" } }));
    expect(body).not.toHaveProperty("skill_slug");
    expect(body).not.toHaveProperty("skill");
  });
});

describe("education", () => {
  it("takes a qualification and an optional year in range", () => {
    const form = { ...blankForm("educations"), qualification: "ITI Electrician", year_completed: "2018", education_level: "iti" };
    expect(ok("educations", form)).toEqual({
      qualification: "ITI Electrician",
      institution: null,
      specialisation: null,
      education_level: "iti",
      year_completed: 2018,
      is_pursuing: false,
    });
    expect(problemFor(bad("educations", { ...form, year_completed: "1900" }), "year_completed")).toBe("year");
    expect(problemFor(bad("educations", { ...form, qualification: "" }), "qualification")).toBe("required");
  });

  it("offers exactly the levels the server accepts", () => {
    const field = FIELDS.educations.find((f) => f.key === "education_level");
    expect(field?.kind === "choice" && field.options).toHaveLength(8);
  });
});

describe("certificates", () => {
  it("dates are optional, but an expiry before the issue is refused", () => {
    const form = { ...blankForm("certifications"), name: "CPR" };
    expect(ok("certifications", form).issued_on).toBeNull();
    const problems = bad("certifications", {
      ...form,
      [monthKey("issued_on")]: "6",
      [yearKey("issued_on")]: "2022",
      [monthKey("expires_on")]: "5",
      [yearKey("expires_on")]: "2022",
    });
    expect(problemFor(problems, "expires_on")).toBe("order");
  });

  it("half a date is a problem, not a silent null", () => {
    const problems = bad("certifications", { ...blankForm("certifications"), name: "CPR", [monthKey("issued_on")]: "6" });
    expect(problemFor(problems, "issued_on")).toBe("date");
  });
});

describe("languages, roles and places", () => {
  it("a language needs at least two letters and starts conversational, reading and writing", () => {
    const blank = blankForm("languages");
    expect(blank.proficiency).toBe("conversational");
    expect(blank.can_read).toBe(true);
    expect(problemFor(bad("languages", { ...blank, language: "H" }), "language")).toBe("short");
    expect(ok("languages", { ...blank, language: "Hindi", proficiency: "native", can_write: false })).toEqual({
      language: "Hindi",
      proficiency: "native",
      can_read: true,
      can_write: false,
    });
  });

  it("a role needs a title, a place needs a state and may name a district", () => {
    expect(problemFor(bad("preferred_roles", blankForm("preferred_roles")), "title")).toBe("required");
    expect(ok("preferred_roles", { title: "Nurse assistant" })).toEqual({ title: "Nurse assistant" });
    expect(ok("preferred_locations", { state: "Maharashtra", district: "" })).toEqual({ state: "Maharashtra", district: null });
    expect(problemFor(bad("preferred_locations", { state: "", district: "Pune" }), "state")).toBe("required");
  });
});

describe("the list line", () => {
  it("names the role, the employer and the months worked", () => {
    const line = summaryOf(
      "experiences",
      { id: "1", role_title: "Ward attendant", employer_name: "Apollo Care", started_on: "2019-04-15", ended_on: "2021-09-30", is_current: false },
      months,
    );
    expect(line).toEqual({ title: "Ward attendant", lines: ["Apollo Care", "Apr 2019 - Sep 2021"] });
  });

  it("a job still held shows only its start", () => {
    const line = summaryOf("experiences", { id: "1", role_title: "A", employer_name: "B", started_on: "2019-04-15", ended_on: "2020-01-01", is_current: true }, months);
    expect(line.lines[1]).toBe("Apr 2019");
  });

  it("a place reads district then state", () => {
    expect(summaryOf("preferred_locations", { id: "1", state: "Maharashtra", district: "Pune" }, months).title).toBe("Pune, Maharashtra");
  });
});

describe("labels", () => {
  // The real catalogues, as the screens read them (the web's `profilePage` namespace).
  const catalogues = { en: require("../messages/en.json"), hi: require("../messages/hi.json") };

  it("every field, in both languages, has a label in the web's own catalogue", () => {
    const { FIELD_LABEL } = jest.requireActual("./profile-sections") as typeof import("./profile-sections");
    for (const [locale, catalogue] of Object.entries(catalogues)) {
      for (const collection of COLLECTIONS) {
        for (const field of FIELDS[collection]) {
          if (field.key === "education_level") continue; // labelled by `profilePage.education`
          const key = FIELD_LABEL[field.key];
          expect(key).toBeDefined();
          expect([locale, field.key, catalogue.profilePage.fields[key]]).toEqual([locale, field.key, expect.any(String)]);
        }
      }
    }
  });

  it("every option of a choice field is named in both languages", () => {
    const { optionKey } = jest.requireActual("./profile-sections") as typeof import("./profile-sections");
    for (const catalogue of Object.values(catalogues) as { profilePage: Record<string, Record<string, string>> }[]) {
      for (const collection of COLLECTIONS) {
        for (const field of FIELDS[collection]) {
          if (field.kind !== "choice") continue;
          for (const option of field.options) {
            const [group, name] = optionKey(field.key, option).split(".");
            expect(typeof catalogue.profilePage[group][name]).toBe("string");
          }
        }
      }
    }
  });
});
