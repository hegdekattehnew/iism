import { describe, expect, it } from "vitest";

import { SEEKER, landingFor } from "@/lib/context";

const seeker = { tenant: { slug: "personal-abc123", tenant_type: "personal" } };
const org = (slug: string, tenant_type = "employer") => ({
  tenant: { slug, tenant_type },
});

describe("landingFor — where a person lands after signing in", () => {
  it("lands on the organisation the sign-in was explicitly for", () => {
    expect(
      landingFor([seeker, org("b"), org("a")], {
        organisationSlug: "b",
        last: SEEKER,
      }),
    ).toBe("/employer/b");
  });

  it("returns a candidate who also hires to wherever they last were", () => {
    // ADR-038's central case. This always went to /matches.
    expect(landingFor([seeker, org("acme")], { last: "acme" })).toBe(
      "/employer/acme",
    );
    expect(landingFor([seeker, org("acme")], { last: SEEKER })).toBe(
      "/matches",
    );
  });

  it("ignores a remembered organisation this account does not hold", () => {
    // A shared phone: the previous person's slug must not steer this one.
    expect(landingFor([seeker], { last: "someone-elses-org" })).toBe(
      "/matches",
    );
  });

  it("ignores an organisation slug it does not hold", () => {
    expect(landingFor([seeker], { organisationSlug: "ghost" })).toBe(
      "/matches",
    );
  });

  it("gives the same answer every time for several organisations", () => {
    // `.find()` over an unordered list landed a multi-org account anywhere.
    expect(landingFor([org("zeta"), org("alpha")])).toBe("/employer/alpha");
    expect(landingFor([org("alpha"), org("zeta")])).toBe("/employer/alpha");
  });

  it("never sends an organisation-only account to the job-seeker side", () => {
    expect(landingFor([org("acme")], { last: SEEKER })).toBe("/employer/acme");
  });
});
