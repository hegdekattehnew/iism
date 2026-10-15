import { configProblems } from "./release";

const GOOD = { apiBaseUrl: "https://api.example.org", webBaseUrl: "https://www.example.org", release: true };

describe("configProblems", () => {
  it("accepts an HTTPS origin for both, in a release build", () => {
    expect(configProblems(GOOD)).toEqual([]);
  });

  it("asks nothing of a development build, whatever it points at", () => {
    expect(configProblems({ apiBaseUrl: undefined, webBaseUrl: undefined, release: false })).toEqual([]);
    expect(configProblems({ apiBaseUrl: "http://10.0.2.2:8000", webBaseUrl: "http://localhost:3000", release: false })).toEqual([]);
  });

  it("refuses a release build with no API origin", () => {
    expect(configProblems({ ...GOOD, apiBaseUrl: undefined })).toContain("api-missing");
    expect(configProblems({ ...GOOD, apiBaseUrl: "" })).toContain("api-missing");
    expect(configProblems({ ...GOOD, apiBaseUrl: "not a url" })).toContain("api-missing");
  });

  it("refuses cleartext HTTP, which Android and iOS both block in a release", () => {
    expect(configProblems({ ...GOOD, apiBaseUrl: "http://api.example.org" })).toEqual(["api-insecure"]);
  });

  it.each([
    "https://localhost:8000",
    "https://127.0.0.1",
    "https://10.0.2.2:8000",
    "https://0.0.0.0",
    "https://[::1]:8000",
    "https://app.localhost",
  ])("refuses a local origin even over HTTPS: %s", (apiBaseUrl) => {
    expect(configProblems({ ...GOOD, apiBaseUrl })).toContain("api-local");
  });

  it("does not mistake a public host that merely contains the word", () => {
    expect(configProblems({ ...GOOD, apiBaseUrl: "https://localhost-api.example.org" })).toEqual([]);
  });

  it("refuses a missing, cleartext or local website (the privacy notice lives there)", () => {
    expect(configProblems({ ...GOOD, webBaseUrl: undefined })).toEqual(["web-missing"]);
    expect(configProblems({ ...GOOD, webBaseUrl: "http://www.example.org" })).toEqual(["web-insecure"]);
    expect(configProblems({ ...GOOD, webBaseUrl: "https://localhost:3000" })).toEqual(["web-local"]);
  });

  it("reports every problem, not only the first", () => {
    expect(
      configProblems({ apiBaseUrl: "http://localhost:8000", webBaseUrl: undefined, release: true }),
    ).toEqual(["api-insecure", "api-local", "web-missing"]);
  });
});
