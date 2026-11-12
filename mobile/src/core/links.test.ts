import { resolveLink } from "./links";

const HOSTS = ["iism.example"];

describe("what a link may open", () => {
  it.each([
    ["iism://job/ward-assistant-1", "/job/ward-assistant-1"],
    ["iism:///job/ward-assistant-1", "/job/ward-assistant-1"],
    ["IISM://course/phlebotomy-1", "/course/phlebotomy-1"],
    ["iism://skill/hand-hygiene-2", "/skill/hand-hygiene-2"],
    ["iism://match/ward-assistant-1", "/match/ward-assistant-1"],
    ["iism://matches", "/matches"],
    ["iism://applications", "/applications"],
    ["iism://notices", "/notices"],
    ["iism://batches", "/batches"],
    ["iism://batches/0b6f6f3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b", "/batches/0b6f6f3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b"],
    ["iism://notifications", "/notices"],
    ["iism://grievance", "/contact"],
    ["iism://", "/"],
    ["iism://invite/AbCdEf12_-xyz", "/invite/AbCdEf12_-xyz"],
  ])("opens %s as %s", (url, path) => {
    expect(resolveLink(url)).toBe(path);
  });

  it("opens a batch only for a real id, and the website's batch path the same way (Sprint 102)", () => {
    expect(resolveLink("/batches/0B6F6F3E-1C2D-4E5F-8A9B-0C1D2E3F4A5B")).toBe(
      "/batches/0b6f6f3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b",
    );
    expect(resolveLink("/batches/not-an-id")).toBeNull();
    expect(resolveLink("/batches/..%2Faccount")).toBeNull();
    expect(resolveLink("/batches/0b6f6f3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b/extra")).toBeNull();
  });

  it("understands the website's own paths, so a notice's path and a shared link both work", () => {
    expect(resolveLink("/jobs/ward-assistant-1")).toBe("/job/ward-assistant-1");
    expect(resolveLink("/courses/phlebotomy-1")).toBe("/course/phlebotomy-1");
    expect(resolveLink("/applications")).toBe("/applications");
    expect(resolveLink("/notifications")).toBe("/notices");
    expect(resolveLink("/grievance")).toBe("/contact");
  });

  it("drops a query, a fragment and a trailing slash", () => {
    expect(resolveLink("iism://job/ward-assistant-1/?utm=x#top")).toBe("/job/ward-assistant-1");
    expect(resolveLink("/applications/")).toBe("/applications");
  });

  it("opens a web link only for a host it was told is the website", () => {
    expect(resolveLink("https://iism.example/jobs/ward-assistant-1", HOSTS)).toBe("/job/ward-assistant-1");
    expect(resolveLink("https://IISM.example/jobs/ward-assistant-1", HOSTS)).toBe("/job/ward-assistant-1");
    expect(resolveLink("https://evil.example/jobs/ward-assistant-1", HOSTS)).toBeNull();
    expect(resolveLink("https://iism.example/jobs/ward-assistant-1")).toBeNull();
  });

  it("never opens a route that is not in the table", () => {
    for (const bad of [
      "iism://sign-in",
      "iism://(tabs)/me",
      "iism://job",
      "iism://job/",
      "iism://job/a/b",
      "iism://admin",
      "/ops/reports",
      "/org/apollo/jobs",
      "/employer/apollo",
      "/sign-in",
    ]) {
      expect(resolveLink(bad)).toBeNull();
    }
  });

  it("refuses a slug the API would never produce, so nothing odd reaches a route parameter", () => {
    for (const bad of ["iism://job/Ward", "iism://job/-x", "iism://job/a b", "iism://job/..", "iism://job/%2e%2e", `iism://job/${"a".repeat(201)}`]) {
      expect(resolveLink(bad)).toBeNull();
    }
  });

  it("refuses an invitation token with odd characters or the wrong length", () => {
    for (const bad of ["iism://invite/short", "iism://invite/has space1234", `iism://invite/${"a".repeat(201)}`]) {
      expect(resolveLink(bad)).toBeNull();
    }
  });

  it("refuses anything that is not a link to an in-app place", () => {
    for (const bad of [
      "//evil.example/jobs/x",
      "https://evil.example",
      "javascript:alert(1)",
      "http://iism.example/jobs/x",
      "file:///etc/passwd",
      "jobs/x",
      "",
      "   ",
    ]) {
      expect(resolveLink(bad, HOSTS)).toBeNull();
    }
    for (const notAString of [null, undefined, 5, {}, ["/jobs/x"]]) {
      expect(resolveLink(notAString)).toBeNull();
    }
    expect(resolveLink(`iism://job/${"a".repeat(3000)}`)).toBeNull();
  });
});
