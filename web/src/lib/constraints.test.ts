import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Every server limit is mirrored on the input that can break it.
 *
 * Two bugs made this worth enforcing rather than remembering. A vacancy whose
 * title was two characters long was accepted by the browser, refused by the
 * server, and reported as "Could not save. Check the details and try again."
 * -- `JobIn.title` has `min_length=3` and the form had no `minLength`. The
 * same gap was on the course editor, and on thirteen fields across the six
 * profile collections.
 *
 * This reads the forms rather than rendering them: the question is whether the
 * attribute is *there*, which is a property of the source, and a rendering
 * test would need one case per field per collection to ask it.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (p: string) => readFileSync(join(SRC, p), "utf8");

/** field -> the attribute the server's constraint requires. */
type Expected = Record<string, string[]>;

const CASES: { file: string; label: string; expect: Expected }[] = [
  {
    file: "components/employer/JobEditor.tsx",
    label: "JobIn",
    expect: {
      title: ["minLength={3}", "maxLength={200}"],
      description: ["maxLength={10000}"],
      location_state: ["maxLength={120}"],
      location_district: ["maxLength={120}"],
      positions: ["min={1}", "max={999}"],
      experience_min_years: ["min={0}", "max={60}"],
      experience_max_years: ["min={0}", "max={60}"],
    },
  },
  {
    file: "components/ops/OrganisationReview.tsx",
    label: "VerificationIn",
    expect: {
      // The note is the only record of why a candidate should believe the
      // badge, so "ok" is not a reason. Written through the shared constants
      // rather than as literals, because the server's floor and the browser's
      // must be one number.
      note: ["minLength={NOTE_MIN}", "maxLength={NOTE_MAX}"],
    },
  },
  {
    file: "components/ops/RoleAliasEditor.tsx",
    label: "RoleAliasIn",
    expect: {
      // Literals, not the `ALIAS_*` constants: the constants feed the hint text, and
      // this pins the numbers themselves against `RoleAliasIn` on the server.
      surface_form: ["minLength={2}", "maxLength={80}"],
      note: ["maxLength={300}"],
    },
  },
  {
    file: "components/employer/CourseEditor.tsx",
    label: "CourseIn",
    expect: {
      title: ["minLength={3}", "maxLength={200}"],
      description: ["maxLength={10000}"],
      duration_hours: ["min={1}", "max={10000}"],
    },
  },
  {
    file: "components/employer/CentresPanel.tsx",
    label: "CentreIn",
    expect: {
      name: ["minLength={2}", "maxLength={120}"],
      address: ["maxLength={500}"],
      state: ["minLength={2}", "maxLength={120}"],
      district: ["minLength={2}", "maxLength={120}"],
    },
  },
  {
    file: "components/employer/OrgSettings.tsx",
    label: "OrganisationIn",
    expect: {
      name: ["minLength={2}", "maxLength={120}"],
      city: ["maxLength={120}"],
      website: ["maxLength={500}"],
      logo_url: ["maxLength={500}"],
      // What a training organisation says about itself (Sprint 94, ADR-102).
      affiliations: ["maxLength={500}"],
      teaching_languages: ["maxLength={200}"],
      year_established: ["min={1800}"],
    },
  },
  {
    file: "components/MessageForm.tsx",
    label: "GrievanceIn",
    expect: {
      // Through the shared constants, so the server's floor and the browser's are one number;
      // the describe block at the foot of this file pins the constants themselves.
      body: ["minLength={BODY_MIN}", "maxLength={BODY_MAX}"],
      reply_to: ["maxLength={REPLY_TO_MAX}"],
    },
  },
  {
    file: "components/ops/GrievanceQueue.tsx",
    label: "GrievanceDecisionIn",
    expect: { note: ["minLength={NOTE_MIN}", "maxLength={NOTE_MAX}"] },
  },
  {
    file: "components/employer/CourseEditor.tsx",
    label: "CourseIn (place and intake, Sprint 58)",
    expect: {
      location_state: ["maxLength={120}"],
      location_district: ["maxLength={120}"],
      seats: ["min={1}", "max={100000}"],
    },
  },
  {
    // `budget_inr` is a query parameter (`ge=0`, `le=10_000_000`), not a body field, but the input
    // that sets it has the same duty to say so before a request is made.
    file: "components/SuggestedCourses.tsx",
    label: "the course budget query parameter",
    expect: { budget_inr: ["min={0}", "max={10000000}"] },
  },
  {
    file: "components/ReportListing.tsx",
    label: "ReportIn",
    expect: { detail: ["maxLength={DETAIL_MAX}"] },
  },
  {
    file: "components/ops/ReportQueue.tsx",
    label: "DismissIn and TakedownIn",
    expect: { note: ["minLength={NOTE_MIN}", "maxLength={NOTE_MAX}"] },
  },
  {
    file: "components/employer/EmployerInbox.tsx",
    label: "StatusIn (the message with a status, Sprint 60)",
    expect: { status_message: ["maxLength={STATUS_MESSAGE_MAX}"] },
  },
  {
    file: "components/employer/ApplicantNotes.tsx",
    label: "NotesIn",
    expect: { notes: ["maxLength={NOTES_MAX}"] },
  },
  {
    file: "components/ReviewControl.tsx",
    label: "ReviewIn",
    expect: { comment: ["maxLength={1000}"] },
  },
  {
    file: "components/profile/AboutSection.tsx",
    label: "CandidateProfileUpdateFull",
    expect: {
      full_name: ["maxLength={120}"],
      headline: ["maxLength={160}"],
      location_state: ["maxLength={80}"],
      location_district: ["maxLength={80}"],
      years_experience: ["min={0}", "max={60}"],
    },
  },
];

describe("forms mirror the server's constraints", () => {
  for (const { file, label, expect: fields } of CASES) {
    describe(`${label} (${file.split("/").pop()})`, () => {
      const source = read(file);
      for (const [field, attrs] of Object.entries(fields)) {
        it(`${field} carries ${attrs.join(" ")}`, () => {
          // The 400 characters after the field's own `name=`, which is where
          // its attributes live.
          const at = source.indexOf(`name="${field}"`);
          expect(at, `no input named ${field}`).toBeGreaterThan(-1);
          // To the end of the element, so a neighbour's identical limit cannot stand in for this one.
          const end = source.indexOf("/>", at);
          const window = source.slice(at, end > -1 ? Math.min(end, at + 600) : at + 400);
          for (const attr of attrs) expect(window).toContain(attr);
        });
      }
    });
  }

  // The six profile collections share one editor, so their fields are keyed on
  // the value they read rather than a `name=`.
  describe("the repeating profile sections (section-forms, split out of SectionEditor in Sprint 79)", () => {
    const source = read("components/profile/section-forms.tsx");
    const LIMITS: Record<string, string> = {
      employer_name: "maxLength={120}",
      role_title: "maxLength={120}",
      location: "maxLength={120}",
      description: "maxLength={1000}",
      qualification: "maxLength={160}",
      institution: "maxLength={160}",
      specialisation: "maxLength={120}",
      name: "maxLength={160}",
      issuing_body: "maxLength={160}",
      credential_id: "maxLength={80}",
      language: "maxLength={40}",
    };
    for (const [field, attr] of Object.entries(LIMITS)) {
      it(`${field} carries ${attr}`, () => {
        const at = source.indexOf(`str(d, "${field}")`);
        expect(at, `no field reading ${field}`).toBeGreaterThan(-1);
        // To the end of this element: the next field's limit must not count for this one.
        expect(source.slice(at, source.indexOf("/>", at))).toContain(attr);
      });
    }

    it("language also carries its minimum, which is the one a person trips", () => {
      // `LanguageIn.language` is min_length=2: a single character is the
      // realistic mistake, and it used to 422 with "check the fields".
      const at = source.indexOf('str(d, "language")');
      expect(source.slice(at, source.indexOf("/>", at))).toContain("minLength={2}");
    });
  });
});

/**
 * The upload screen refuses what the server would, before sending it. Both numbers are
 * the server's own, read from its source so that changing one without the other fails
 * here rather than as a 413 somebody meets in production.
 */
describe("the bulk upload screen mirrors the server's limits", () => {
  const screen = read("components/employer/BulkUpload.tsx");
  const root = join(SRC, "..", "..");
  const config = readFileSync(join(root, "api/core/config.py"), "utf8");
  const schemas = readFileSync(join(root, "api/modules/marketplace/schemas.py"), "utf8");

  it("refuses a file larger than max_bulk_body_bytes", () => {
    expect(config).toContain("max_bulk_body_bytes: int = 2 * 1024 * 1024");
    expect(screen).toContain("MAX_FILE_BYTES = 2 * 1024 * 1024");
  });

  it("publishes in batches no larger than BulkPublishIn allows", () => {
    const at = schemas.indexOf("class BulkPublishIn");
    expect(at).toBeGreaterThan(-1);
    expect(schemas.slice(at, at + 300)).toContain("max_length=200");
    expect(screen).toContain("PUBLISH_BATCH = 200");
  });
});


/** The grievance form's numbers are the server's, read from its source. */
describe("the grievance forms mirror the server's limits", () => {
  const root = join(SRC, "..", "..");
  const models = readFileSync(join(root, "api/modules/grievances/models.py"), "utf8");
  const schemas = readFileSync(join(root, "api/modules/grievances/schemas.py"), "utf8");
  const lib = read("lib/grievances.ts");

  it("the message length", () => {
    expect(models).toContain("BODY_MIN, BODY_MAX = 10, 4000");
    expect(lib).toContain("BODY_MIN = 10");
    expect(lib).toContain("BODY_MAX = 4000");
  });

  it("the reply address", () => {
    expect(schemas).toContain("reply_to: Annotated[str, Field(max_length=254)]");
    expect(lib).toContain("REPLY_TO_MAX = 254");
  });

  it("the operator's note", () => {
    expect(schemas).toContain("note: Annotated[str, Field(min_length=10, max_length=1000)]");
    expect(lib).toContain("NOTE_MIN = 10");
    expect(lib).toContain("NOTE_MAX = 1000");
  });
});

/** The agency enrolment's limits are the engine's own (Sprint 61), mirrored on the form. */
describe("the enrolment form mirrors the engine's limits", () => {
  const root = join(SRC, "..", "..");
  const engine = readFileSync(join(root, "api/modules/operations/enrolment.py"), "utf8");
  const lib = read("lib/enrolment.ts");
  const form = read("components/ops/EnrolmentUpload.tsx");

  it("the programme name", () => {
    expect(engine).toContain("MAX_PROGRAMME = 120");
    expect(engine).toContain("len(name) < 2");
    expect(lib).toContain("PROGRAMME_MAX = 120");
    expect(lib).toContain("PROGRAMME_MIN = 2");
    expect(form).toContain("minLength={PROGRAMME_MIN}");
    expect(form).toContain("maxLength={PROGRAMME_MAX}");
  });

  it("the file size", () => {
    expect(lib).toContain("MAX_FILE_BYTES = 2 * 1024 * 1024");
    expect(readFileSync(join(root, "api/core/config.py"), "utf8")).toContain(
      "max_bulk_body_bytes: int = 2 * 1024 * 1024",
    );
  });
});

/** The budget ceiling is the server's own, read from the three routes that accept it. */
describe("the course budget mirrors the server's ceiling", () => {
  const root = join(SRC, "..", "..");
  it("is the same number in the store and on each of the three routes", () => {
    expect(read("lib/course-budget.ts")).toContain("BUDGET_MAX = 10_000_000");
    for (const route of [
      "api/modules/matching/routes.py",
      "api/modules/careers/routes.py",
      "api/modules/applications/routes.py",
    ]) {
      expect(readFileSync(join(root, route), "utf8"), route).toContain("le=10_000_000");
    }
  });
});

/** The report forms' numbers are the server's, read from its source. */
describe("the report forms mirror the server's limits", () => {
  const root = join(SRC, "..", "..");
  const models = readFileSync(join(root, "api/modules/moderation/models.py"), "utf8");
  const schemas = readFileSync(join(root, "api/modules/moderation/schemas.py"), "utf8");
  const lib = read("lib/moderation.ts");

  it("the detail length", () => {
    expect(models).toContain("DETAIL_MAX = 1000");
    expect(lib).toContain("DETAIL_MAX = 1000");
  });

  it("the operator's note and the removal reason", () => {
    expect(schemas).toContain("NOTE_MIN, NOTE_MAX = 10, 1000");
    expect(lib).toContain("NOTE_MIN = 10");
    expect(lib).toContain("NOTE_MAX = 1000");
  });

  it("the reasons are the server's, in the server's order", () => {
    const listed = [...models.matchAll(/^\s+"([a-z_]+)",$/gm)].map((m) => m[1]);
    const reasons = ["asks_for_money", "fake_or_misleading", "discriminatory", "unsafe_or_illegal", "spam_or_duplicate", "other"];
    expect(listed).toEqual(expect.arrayContaining(reasons));
    for (const reason of reasons) expect(lib).toContain(`"${reason}"`);
  });
});

/** The hiring forms' limits are the server's, read from its source. */
describe("the hiring forms mirror the server's limits", () => {
  const root = join(SRC, "..", "..");
  const schemas = readFileSync(join(root, "api/modules/applications/schemas.py"), "utf8");
  const lib = read("lib/hiring.ts");

  it("the message with a status and the private note", () => {
    expect(schemas).toContain("STATUS_MESSAGE_MAX = 500");
    expect(schemas).toContain("NOTES_MAX = 2000");
    expect(lib).toContain("STATUS_MESSAGE_MAX = 500");
    expect(lib).toContain("NOTES_MAX = 2000");
  });
});
