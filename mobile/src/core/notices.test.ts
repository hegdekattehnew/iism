import type { Translate } from "./labels";
import { NOTICE_PAGE_SIZE, nextCursor, noticePath, noticeText } from "./notices";

/** A translator that shows its key and values, so which words were chosen is visible. */
const t: Translate = (key, values) =>
  values
    ? `${key}(${Object.entries(values)
        .map(([k, v]) => `${k}=${v}`)
        .join(",")})`
    : key;

const notice = (template: string, payload: Record<string, unknown> = {}) => ({ template, payload });

describe("a notice in words", () => {
  it("says an application moved, naming the vacancy, the organisation and the new status", () => {
    expect(
      noticeText(notice("application_status_changed", { vacancy: "Ward assistant", organisation: "Apollo", status: "shortlisted" }), t),
    ).toBe("statusChanged(vacancy=Ward assistant,organisation=Apollo,status=status.shortlisted)");
  });

  it("says there is a message, and never carries the message", () => {
    const text = noticeText(
      notice("application_status_message", { vacancy: "V", organisation: "O", status: "rejected", message: "Call me on 9876543210" }),
      t,
    );
    expect(text).toContain("statusMessage");
    expect(text).not.toContain("9876543210");
  });

  it.each([
    ["job_alert", { vacancy: "V", organisation: "O" }, "jobAlert(vacancy=V,organisation=O)"],
    ["vacancy_closed", { vacancy: "V" }, "vacancyClosed(vacancy=V)"],
    [
      "course_interest_status_changed",
      { course: "C", organisation: "O", status: "enrolled" },
      "interestStatusChanged(course=C,organisation=O,status=interestStatus.enrolled)",
    ],
    [
      "sponsor_offer",
      { organisation: "O", vacancy: "V", standard: "S", course: "C" },
      "sponsorOffer(organisation=O,vacancy=V,standard=S,course=C)",
    ],
    [
      "grievance_update",
      { reference: "G-1", status: "resolved" },
      "grievanceUpdate(reference=G-1,status=grievanceStatus.resolved)",
    ],
  ])("words %s with its own sentence", (template, payload, expected) => {
    expect(noticeText(notice(template, payload), t)).toBe(expected);
  });

  describe("a batch the person asked about (Sprint 102)", () => {
    const day = (iso: string) => (iso === "2026-11-09" ? "9 Nov 2026" : null);

    it.each([
      [
        "batch_cancelled",
        { course: "C", reason: "centre_closed" },
        "batchCancelled(course=C,reason=batchReason.centre_closed)",
      ],
      [
        "batch_interest_status_changed",
        { course: "C", organisation: "O", status: "enrolled" },
        "batchInterestStatusChanged(course=C,organisation=O,status=batchInterestStatus.enrolled)",
      ],
      ["batch_full", { course: "C", centre: "H" }, "batchFull(course=C,centre=H)"],
    ])("words %s with its own sentence", (template, payload, expected) => {
      expect(noticeText(notice(template, payload), t, day)).toBe(expected);
    });

    it("says whether the learner holds a seat when the batch starts, and the day in words", () => {
      const starts = { course: "C", centre: "H", starts_on: "2026-11-09" };
      expect(noticeText(notice("batch_starting", { ...starts, enrolled: true }), t, day)).toBe(
        "batchStarting(course=C,centre=H,date=9 Nov 2026)",
      );
      expect(noticeText(notice("batch_starting", { ...starts, enrolled: false }), t, day)).toBe(
        "batchStartingWaiting(course=C,centre=H,date=9 Nov 2026)",
      );
    });

    it("leaves the date out rather than guessing it, and never reads a number as a seat", () => {
      expect(noticeText(notice("batch_starting", { course: "C", centre: "H", starts_on: "soon", enrolled: true }), t, day)).toBe(
        "batchStarting(course=C,centre=H,date=)",
      );
      expect(noticeText(notice("batch_starting", { course: "C", centre: "H", enrolled: "yes" }), t)).toContain("batchStartingWaiting");
    });

    it("opens the batch's own page from the notice's path, and nothing else", () => {
      const id = "0b6f6f3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b";
      expect(noticePath(notice("batch_full", { path: `/batches/${id}` }))).toBe(`/batches/${id}`);
      expect(noticePath(notice("batch_full", { path: "/batches/x" }))).toBeNull();
    });
  });

  it("says the generic line for a template it does not know, never nothing", () => {
    expect(noticeText(notice("something_new", { vacancy: "V" }), t)).toBe("generic");
  });

  it("copes with a payload that is missing a field", () => {
    expect(noticeText(notice("job_alert"), t)).toBe("jobAlert(vacancy=,organisation=)");
    expect(noticeText({ template: "vacancy_closed", payload: undefined as never }, t)).toBe("vacancyClosed(vacancy=)");
  });
});

describe("where a notice points", () => {
  it("opens the in-app screen for a website path", () => {
    expect(noticePath(notice("application_status_changed", { path: "/applications" }))).toBe("/applications");
    expect(noticePath(notice("job_alert", { path: "/jobs/ward-assistant-1" }))).toBe("/job/ward-assistant-1");
  });

  it("points a grievance update at its fixed page, whatever the payload says", () => {
    expect(noticePath(notice("grievance_update", { path: "/ops/reports" }))).toBe("/contact");
  });

  it("never follows a path that leaves the app", () => {
    for (const path of ["https://evil.example", "//evil.example", "javascript:alert(1)", "/ops/queue", 5, null, undefined]) {
      expect(noticePath(notice("job_alert", { path }))).toBeNull();
    }
    expect(noticePath(notice("job_alert"))).toBeNull();
  });
});

describe("paging older notices", () => {
  const row = (n: number) => ({ id: `id${n}`, created_at: `2026-10-${String(n).padStart(2, "0")}T10:00:00Z` });

  it("asks for what is older than the last one, by its time and its id", () => {
    const page = Array.from({ length: NOTICE_PAGE_SIZE }, (_, i) => row(30 - i));
    expect(nextCursor(page)).toEqual({ before: "2026-10-01T10:00:00Z", before_id: "id1" });
  });

  it("stops when a page comes back short", () => {
    expect(nextCursor([row(3), row(2)])).toBeUndefined();
    expect(nextCursor([])).toBeUndefined();
  });
});
