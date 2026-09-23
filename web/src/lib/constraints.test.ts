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
    file: "components/employer/CourseEditor.tsx",
    label: "CourseIn",
    expect: {
      title: ["minLength={3}", "maxLength={200}"],
      description: ["maxLength={10000}"],
      duration_hours: ["min={1}", "max={10000}"],
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
    },
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
          const window = source.slice(at, at + 400);
          for (const attr of attrs) expect(window).toContain(attr);
        });
      }
    });
  }

  // The six profile collections share one editor, so their fields are keyed on
  // the value they read rather than a `name=`.
  describe("the six profile collections (SectionEditor)", () => {
    const source = read("components/profile/SectionEditor.tsx");
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
        expect(source.slice(at, at + 200)).toContain(attr);
      });
    }

    it("language also carries its minimum, which is the one a person trips", () => {
      // `LanguageIn.language` is min_length=2: a single character is the
      // realistic mistake, and it used to 422 with "check the fields".
      const at = source.indexOf('str(d, "language")');
      expect(source.slice(at, at + 200)).toContain("minLength={2}");
    });
  });
});
