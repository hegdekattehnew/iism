import { canDelete, consentOf, exportFile, type DeletionPreview } from "./account";

const fate = (name: string) => ({ slug: name.toLowerCase(), name, listings: 2 });

describe("the file a person takes away", () => {
  it("is named for what it is and the day, and is the whole document, indented", () => {
    const file = exportFile({ account: { id: "u1" }, devices: [{ platform: "ios" }] }, "2026-10-15");
    expect(file.filename).toBe("iism-my-data-2026-10-15.json");
    expect(JSON.parse(file.text)).toEqual({ account: { id: "u1" }, devices: [{ platform: "ios" }] });
    expect(file.text).toContain("\n  ");
  });

  it("is exactly what the server said, so a token the server never sent cannot appear", () => {
    const server = { devices: [{ platform: "android", locale: "en" }] };
    expect(exportFile(server, "2026-10-15").text).not.toContain("token");
  });
});

describe("deleting the account", () => {
  const preview = (over: Partial<DeletionPreview> = {}): DeletionPreview => ({
    organisations_deleted: [],
    blocked_by: [],
    ...over,
  });

  it("may go ahead when nothing blocks it", () => {
    expect(canDelete(preview())).toBe(true);
    expect(canDelete(preview({ organisations_deleted: [fate("Apollo")] }))).toBe(true);
  });

  it("may not while the person is the only owner of an organisation others belong to", () => {
    expect(canDelete(preview({ blocked_by: [fate("Apollo")] }))).toBe(false);
  });
});

describe("what was agreed to", () => {
  it("names the notice version and when, once both are recorded", () => {
    expect(consentOf({ consent_version: "2026-09-11", consented_at: "2026-10-01T10:00:00Z" })).toEqual({
      version: "2026-09-11",
      at: "2026-10-01T10:00:00Z",
    });
  });

  it("says nothing was recorded rather than inventing it", () => {
    expect(consentOf({})).toBeNull();
    expect(consentOf({ consent_version: "2026-09-11", consented_at: null })).toBeNull();
  });
});
