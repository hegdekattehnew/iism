import { render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CourseDetailPage from "@/app/[locale]/courses/[slug]/page";
import JobDetailPage from "@/app/[locale]/jobs/[slug]/page";
import ProviderPage from "@/app/[locale]/providers/[slug]/page";
import SkillDetailPage from "@/app/[locale]/skills/[slug]/page";
import { resetWorld } from "@/test/harness";
import messages from "@/messages/en.json";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NOT_FOUND");
  },
}));
// The server's own translator and formatter, built from the same English catalogue the page reads.
vi.mock("next-intl/server", async () => {
  const intl = await import("next-intl");
  const en = (await import("@/messages/en.json")).default;
  return {
    getLocale: async () => "en",
    getTranslations: async (ns: string) => intl.createTranslator({ locale: "en", messages: en, namespace: ns as never }),
    getFormatter: async () => intl.createFormatter({ locale: "en", timeZone: "Asia/Kolkata" }),
  };
});
// Interactive panels are not what these tests are about.
vi.mock("@/components/ApplyPanel", () => ({ ApplyPanel: () => <div data-testid="apply-panel" /> }));
vi.mock("@/components/InterestPanel", () => ({ InterestPanel: () => <div data-testid="interest-panel" /> }));
vi.mock("@/components/ReportListing", () => ({ ReportListing: () => <div data-testid="report-form" /> }));
vi.mock("@/components/SkillRequirements", () => ({ SkillRequirements: () => null }));
vi.mock("@/components/SkillQualifications", () => ({ SkillQualifications: () => null }));
vi.mock("@/components/SkillRelated", () => ({ SkillRelated: () => null }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

const JOB = {
  slug: "gda-chennai",
  title: "General Duty Assistant",
  description: "Look after patients on the ward.",
  location_state: "Tamil Nadu",
  location_district: "Chennai",
  employment_type: "full_time",
  experience_min_years: 0,
  experience_max_years: 2,
  salary_min_inr: 220000,
  salary_max_inr: 300000,
  closes_at: null,
  published_at: null,
  nsqf_level_min: 3,
  is_open: true,
  tenant: { name: "Apollo Care", is_verified: true },
  skills: [
    { skill: { slug: "hand-hygiene", name: "Hand hygiene" }, is_mandatory: true, importance: 5 },
    { skill: { slug: "bed-making", name: "Bed making" }, is_mandatory: false, importance: 3 },
  ],
};

const COURSE = {
  slug: "gda-certificate",
  title: "GDA certificate",
  description: "Learn the basics of ward care.",
  mode: "offline",
  language: "en",
  duration_hours: 120,
  fee_inr: 5000,
  nsqf_level: 4,
  location_state: "Karnataka",
  location_district: "Bengaluru",
  starts_on: "2026-12-01",
  started: false,
  seats_left: 8,
  qualification_name: "General Duty Assistant",
  qualification_credits: 12,
  tenant: { name: "NSDC Academy", slug: "nsdc-academy", is_verified: false },
  skills: [{ skill: { slug: "hand-hygiene", name: "Hand hygiene" }, level_taught: 4 }],
};

async function show(page: Promise<React.ReactElement>) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages} timeZone="Asia/Kolkata">
      {await page}
    </NextIntlClientProvider>,
  );
}

/** The strip's tile, found from its sentence (an organisation's mark may also be green, by its name). */
function tileOf(statement: string): HTMLElement {
  return screen.getByText(statement).parentElement!.parentElement!.firstElementChild as HTMLElement;
}

function serve(data: unknown, rating: { average: number; count: number } | null = null) {
  GET.mockImplementation(async (path: string) => {
    if (path.endsWith("poster-rating")) return { data: { rating }, response: { status: 200 } };
    return { data, response: { status: 200 } };
  });
}

/** Sprint 85, BL-19.15: the three detail pages on the shared pieces. */
describe("the vacancy page", () => {
  it("shows its facts in a description list with an icon on each label", async () => {
    serve(JOB);
    const { container } = await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    const facts = container.querySelector("dl") as HTMLElement;
    expect(facts).toBeTruthy();
    const terms = [...facts.querySelectorAll("dt")];
    expect(terms.map((t) => t.textContent)).toEqual(["Salary", "Experience"]);
    for (const dt of terms) expect(dt.querySelector("[aria-hidden='true'] svg")).toBeTruthy();
    expect(within(facts).getByText("About ₹18,300–25,000 a month")).toBeTruthy();
  });

  it("puts the employer's mark beside who and where, and the words are unchanged", async () => {
    serve(JOB);
    const { container } = await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Apollo Care · Chennai, Tamil Nadu")).toBeTruthy();
    const mark = [...container.querySelectorAll("[aria-hidden='true']")].find((e) => e.textContent === "A");
    expect(mark).toBeTruthy();
  });

  it("says 'verified' or 'not yet verified' in the strip, with the report link on its own 44 px line", async () => {
    serve(JOB);
    const a = await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Verified employer")).toBeTruthy();
    // the tile is the shield on green for a verified employer: the words and the shape agree
    expect(tileOf("Verified employer").className).toContain("bg-success-surface");
    const link = screen.getByRole("link", { name: /Report/ });
    expect(link.getAttribute("href")).toBe("#report");
    expect(link.className).toContain("min-h-11");
    a.unmount();
    serve({ ...JOB, tenant: { name: "Apollo Care", is_verified: false } });
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Not yet verified")).toBeTruthy();
    expect(tileOf("Not yet verified").className).not.toContain("bg-success-surface");
  });

  it("keeps the type, the level and (when near) the closing date as chips with an icon", async () => {
    serve({ ...JOB, closes_at: new Date(Date.now() + 3 * 86_400_000 - 1000).toISOString() });
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    for (const text of ["Full time", "NSQF level 3 and above", "Closes in 3 days"]) {
      const chip = screen.getByText(text);
      expect(chip.querySelector("svg"), String(text)).toBeTruthy();
    }
  });

  it("lists each required standard as a 44 px link, mandatory ones marked, with a chevron", async () => {
    serve(JOB);
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    const rows = screen.getAllByRole("link", { name: /Hand hygiene|Bed making/ });
    expect(rows.length).toBe(2);
    for (const row of rows) {
      expect(row.className).toContain("min-h-11");
      expect(row.querySelector("svg")).toBeTruthy();
    }
    expect(within(rows[0]).getByText("Must have")).toBeTruthy();
    expect(within(rows[1]).queryByText("Must have")).toBeNull();
  });

  /** Sprint 92, B22.4: "4 out of 5 from 1 rating" read as a verdict on an organisation. */
  it("shows the employer's score from three ratings", async () => {
    serve(JOB, { average: 4.3, count: 3 });
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Rated by workers: 4.3 out of 5 from 3 ratings")).toBeTruthy();
  });

  it("withholds the score below three ratings, and says why", async () => {
    serve(JOB, { average: 4, count: 1 });
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Rated by workers: not enough ratings yet to show a score")).toBeTruthy();
    expect(screen.queryByText(/out of 5/)).toBeNull();
  });

  it("says nothing about ratings when there are none", async () => {
    serve(JOB, null);
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.queryByText(/Rated by workers/)).toBeNull();
  });

  it("says what the verified mark means, only for a verified employer", async () => {
    serve(JOB);
    const a = await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.getByText("Reviewed by our team.")).toBeTruthy();
    a.unmount();
    serve({ ...JOB, tenant: { name: "Apollo Care", is_verified: false } });
    await show(JobDetailPage({ params: Promise.resolve({ slug: "gda-chennai" }) }));
    expect(screen.queryByText("Reviewed by our team.")).toBeNull();
  });

  it("is a 404 for an unknown vacancy", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 404 } });
    await expect(JobDetailPage({ params: Promise.resolve({ slug: "nope" }) })).rejects.toThrow("NOT_FOUND");
  });
});

describe("the course page", () => {
  it("shows fee, length, place, start, qualification and seats as facts with an icon each", async () => {
    serve(COURSE);
    const { container } = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const terms = [...container.querySelectorAll("dl dt")];
    expect(terms.map((t) => t.textContent)).toEqual(["Fee", "Duration", "Where", "Next intake", "Counts toward", "Places"]);
    for (const dt of terms) expect(dt.querySelector("[aria-hidden='true'] svg")).toBeTruthy();
  });

  it("gives the qualification the whole row and says it is the provider's statement", async () => {
    serve(COURSE);
    const { container } = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const wide = [...container.querySelectorAll("dl > div")].find((d) => d.querySelector("dt")?.textContent?.includes("Counts"));
    expect(wide?.className).toContain("col-span-full");
    expect(within(wide as HTMLElement).getByText(/General Duty Assistant/)).toBeTruthy();
    expect(within(wide as HTMLElement).getByText("Stated by the provider.", { exact: false })).toBeTruthy();
  });

  it("makes each skill taught a 44 px link", async () => {
    serve(COURSE);
    await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const chip = screen.getByRole("link", { name: /Hand hygiene/ });
    expect(chip.className).toContain("min-h-11");
  });

  it("does not call a started group an intake, or offer its seats", async () => {
    // Sprint 91: "Next intake: Started September 29, 2026 . 40 seats left", for a course three weeks in.
    serve({ ...COURSE, starts_on: "2026-09-29", started: true, seats_left: 40 });
    const { container } = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const labels = [...container.querySelectorAll("dl dt")].map((t) => t.textContent);
    expect(labels).not.toContain("Next intake");
    expect(labels).toContain("Started");
    expect(labels).not.toContain("Places");
    expect(screen.getByText("September 29, 2026")).toBeTruthy();
    expect(screen.getByText(/Ask the provider whether you can still join/)).toBeTruthy();
    expect(screen.queryByText(/seats left/)).toBeNull();
  });

  it("still says Full for a started group with no places left", async () => {
    serve({ ...COURSE, starts_on: "2026-09-29", started: true, seats_left: 0 });
    await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    expect(screen.getByText("Full")).toBeTruthy();
  });

  it("keeps Next intake, the start date and the seats for a group that has not begun", async () => {
    serve(COURSE);
    const { container } = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    expect(screen.getByText("Starts December 1, 2026")).toBeTruthy();
    expect(screen.getByText("8 seats left")).toBeTruthy();
    expect(container.textContent).not.toMatch(/Ask the provider whether you can still join/);
  });

  it("never lists a place for an online course", async () => {
    serve({ ...COURSE, mode: "online" });
    const { container } = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const labels = [...container.querySelectorAll("dl dt")].map((t) => t.textContent);
    expect(labels.some((l) => l?.startsWith("Where"))).toBe(false);
  });

  it("says what a provider's verified mark means, and only for a verified provider", async () => {
    serve({ ...COURSE, tenant: { name: "NSDC Academy", is_verified: true } });
    const a = await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    expect(screen.getByText("Reviewed by our team.")).toBeTruthy();
    a.unmount();
    serve(COURSE);
    await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    expect(screen.queryByText("Reviewed by our team.")).toBeNull();
  });

  it("has the provider's strip: not yet verified, free to register, a 44 px report link", async () => {
    serve(COURSE);
    await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    expect(screen.getByText("Provider not yet verified")).toBeTruthy();
    expect(tileOf("Provider not yet verified").className).not.toContain("bg-success-surface");
    expect(screen.getByRole("link", { name: /Report/ }).className).toContain("min-h-11");
    expect(screen.getByTestId("interest-panel")).toBeTruthy();
  });
});

describe("the course page links its organisation", () => {
  it("makes the organisation's name a 44 px link to its own page", async () => {
    serve(COURSE);
    await show(CourseDetailPage({ params: Promise.resolve({ slug: "gda-certificate" }) }));
    const link = screen.getByRole("link", { name: "NSDC Academy" });
    expect(link.getAttribute("href")).toBe("/providers/nsdc-academy");
    expect(link.className).toContain("min-h-11");
  });
});

const PROVIDER = {
  slug: "nsdc-academy",
  name: "NSDC Academy",
  city: "Pune",
  description: "We train ward staff.",
  website: "https://nsdc-academy.example/about",
  logo_url: null,
  is_verified: true,
  publishes_courses: true,
  delivers_training: true,
  year_established: 2005,
  affiliations: "NSDC training partner",
  teaching_languages: "Hindi, English",
  sectors: [{ name: "Healthcare", courses: 2 }],
  courses: [{ ...COURSE, tenant: { name: "NSDC Academy", city: "Pune" } }],
  courses_total: 2,
};

/** Sprint 94, ADR-102: a training organisation's own page. */
describe("the training organisation's page", () => {
  const page = (slug = "nsdc-academy") => ProviderPage({ params: Promise.resolve({ slug }) });

  it("says what it does as two badges, one for each capability it has", async () => {
    serve(PROVIDER);
    const a = await show(page());
    expect(screen.getByText("Sells courses")).toBeTruthy();
    expect(screen.getByText("Delivers training")).toBeTruthy();
    a.unmount();
    serve({ ...PROVIDER, publishes_courses: false });
    await show(page());
    expect(screen.queryByText("Sells courses")).toBeNull();
    expect(screen.getByText("Delivers training")).toBeTruthy();
  });

  it("shows its claims as its own, labelled, and the sectors read from its courses", async () => {
    serve(PROVIDER);
    await show(page());
    const labels = [...document.querySelectorAll("dt")].map((d) => d.textContent);
    expect(labels).toEqual(expect.arrayContaining(["City", "Established", "Teaches in", "Website", "Affiliations"]));
    expect(screen.getByText("NSDC training partner")).toBeTruthy();
    expect(screen.getByText(/Stated by the organisation\. We have not checked it\./)).toBeTruthy();
    expect(screen.getByText("Healthcare")).toBeTruthy();
    expect(screen.getByText("2 courses")).toBeTruthy();
    expect(screen.getByText("Read from the courses it has published.")).toBeTruthy();
  });

  it("lists its open centres, each with its own address mark only when it has one", async () => {
    serve({
      ...PROVIDER,
      centres: [
        { slug: "nsdc-hadapsar", name: "Hadapsar", address: "12 Main Road", location_district: "Pune", location_state: "Maharashtra", is_verified: true },
        { slug: "nsdc-nagpur", name: "Nagpur", address: null, location_district: "Nagpur", location_state: "Maharashtra", is_verified: false },
      ],
    });
    await show(page());
    expect(screen.getByText("Centres (2)")).toBeTruthy();
    expect(screen.getByText("Hadapsar")).toBeTruthy();
    expect(screen.getByText("12 Main Road · Pune, Maharashtra")).toBeTruthy();
    // One checked centre, one mark: a card never says an address is unchecked.
    expect(screen.getAllByText("Address checked")).toHaveLength(1);
    expect(screen.queryByText(/address not checked|unchecked/i)).toBeNull();
  });

  it("says it has listed no centres when it delivers training and has none, and nothing when it does not", async () => {
    serve({ ...PROVIDER, centres: [] });
    const a = await show(page());
    expect(screen.getByText("It has not listed any centres yet.")).toBeTruthy();
    a.unmount();
    serve({ ...PROVIDER, delivers_training: false, centres: [] });
    await show(page());
    expect(screen.queryByText("It has not listed any centres yet.")).toBeNull();
    expect(screen.queryByText(/^Centres/)).toBeNull();
  });

  it("lists its published courses on the same card as the list", async () => {
    serve(PROVIDER);
    await show(page());
    expect(screen.getByText("Courses it sells (2)")).toBeTruthy();
    expect(screen.getByRole("link", { name: /GDA certificate/ }).getAttribute("href")).toBe("/courses/gda-certificate");
    expect(screen.getByText("Showing 1 of 2 courses.")).toBeTruthy();
  });

  it("says whether it is verified, and what that means only when it is", async () => {
    serve(PROVIDER);
    const a = await show(page());
    expect(screen.getByText("Verified training organisation")).toBeTruthy();
    expect(screen.getByText("Reviewed by our team.")).toBeTruthy();
    a.unmount();
    serve({ ...PROVIDER, is_verified: false });
    await show(page());
    expect(screen.getByText("Not yet verified")).toBeTruthy();
    expect(screen.queryByText("Reviewed by our team.")).toBeNull();
  });

  it("links the website only if it is a web address, and safely", async () => {
    serve(PROVIDER);
    const a = await show(page());
    const link = screen.getByRole("link", { name: "nsdc-academy.example/about" });
    expect(link.getAttribute("href")).toBe("https://nsdc-academy.example/about");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.getAttribute("rel")).toContain("nofollow");
    a.unmount();
    serve({ ...PROVIDER, website: "javascript:alert(1)" });
    await show(page());
    expect(document.querySelector('a[href^="javascript"]')).toBeNull();
    expect(screen.queryByText("Website")).toBeNull();
  });

  it("is still a page for an organisation that delivers and sells nothing yet", async () => {
    serve({
      ...PROVIDER,
      publishes_courses: false,
      year_established: null,
      affiliations: null,
      teaching_languages: null,
      website: null,
      city: null,
      description: null,
      sectors: [],
      courses: [],
      courses_total: 0,
    });
    await show(page());
    expect(screen.getByText("It delivers training and sells no courses of its own.")).toBeTruthy();
    expect(document.querySelector("dl")).toBeNull();
    expect(screen.queryByText("Trains in")).toBeNull();
  });

  it("says a seller has no courses yet in the seller's words", async () => {
    serve({ ...PROVIDER, courses: [], courses_total: 0, sectors: [] });
    await show(page());
    expect(screen.getByText("It has no published courses yet.")).toBeTruthy();
  });

  it("is a 404 for an unknown organisation, and an outage is not a 404", async () => {
    GET.mockImplementation(async () => ({ error: {}, response: { status: 404 } }));
    await expect(page("missing")).rejects.toThrow("NOT_FOUND");
    GET.mockImplementation(async () => ({ error: {}, response: { status: 503 } }));
    await expect(page("down")).rejects.toThrow("API responded 503");
  });
});

describe("the standard page", () => {
  it("draws the kind and the level as chips with an icon, and the retired notice with a warning shape", async () => {
    serve({
      slug: "hand-hygiene",
      name: "Hand hygiene",
      description: "Wash hands.",
      skill_type: "technical",
      nsqf_level: 4,
      nos_code: "HSS/N5113",
      nos_version: "1.0",
      source: "legacy",
      aliases: [],
    });
    await show(SkillDetailPage({ params: Promise.resolve({ slug: "hand-hygiene" }) }));
    expect(screen.getByText("Technical").querySelector("svg")).toBeTruthy();
    expect(screen.getByText("NSQF level 4").querySelector("svg")).toBeTruthy();
    const notice = screen.getByText(/no longer|retired|superseded/i);
    expect(notice.querySelector("svg")).toBeTruthy();
  });
});
