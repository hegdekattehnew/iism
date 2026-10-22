import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VerificationQueue } from "@/components/ops/VerificationQueue";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() },
}));

const ROW = {
  slug: "apollo-care-hospitals",
  name: "Apollo Care Hospitals",
  tenant_type: "employer",
  city: "Chennai",
  website: "https://apollo-care.example",
  created_at: "2026-09-02T08:38:17Z",
  jobs: 5,
  courses: 0,
  members: 3,
};

/** The queue answers a page and the size of the whole queue (Sprint 69, UI-17). */
function answer(rows: unknown[] | null, total?: number) {
  GET.mockImplementation(async (_path: string, init?: { params?: { query?: { offset?: number } } }) => {
    if (rows === null) return { data: undefined, error: {}, response: { status: 500 } };
    const offset = init?.params?.query?.offset ?? 0;
    return {
      data: { items: offset === 0 ? rows : [], total: total ?? rows.length, limit: 100, offset },
      error: null,
      response: { status: 200 },
    };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  answer([ROW]);
});

describe("the verification queue", () => {
  it("says the queue is answered rather than rendering an empty list", async () => {
    // An empty list and a finished queue look identical without this, and the
    // second is the one worth telling somebody about.
    answer([]);
    renderUi(<VerificationQueue />);
    expect(
      await screen.findByText(/Every organisation has been decided on/),
    ).toBeTruthy();
  });

  it("links each organisation to its own review page", async () => {
    renderUi(<VerificationQueue />);
    const link = await screen.findByRole("link", { name: "Apollo Care Hospitals" });
    expect(link.getAttribute("href")).toBe("/admin/apollo-care-hospitals");
  });

  it("shows what the organisation has actually done here", async () => {
    // Verifying an employer with no vacancies and no members is verifying an
    // intention, so the counts are on the row rather than a click away.
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/5 vacancies · 0 courses · 3 members/)).toBeTruthy();
  });

  it("says so when a field the operator would look for is missing", async () => {
    answer([{ ...ROW, city: null, website: null }]);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/No city given/)).toBeTruthy();
    expect(screen.getByText("No website given")).toBeTruthy();
  });

  it("reports a failure instead of showing an empty queue", async () => {
    // "Nothing is waiting" is the most misleading thing this screen could say
    // when the truth is that it could not ask.
    answer(null);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/queue could not be loaded/)).toBeTruthy();
  });

  it("says how many are waiting in all, not how many are on the page", async () => {
    // The bug: the cap of 100 printed as "100 waiting" beside an overview that said 162.
    answer([ROW], 162);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/Showing 1 of 162 organisations waiting/)).toBeTruthy();
    expect(screen.queryByText(/^1 organisation waiting/)).toBeNull();
  });

  it("offers the rest, and a count of how many are left", async () => {
    answer([ROW], 162);
    renderUi(<VerificationQueue />);
    expect(await screen.findByRole("button", { name: "Show more (161 left)" })).toBeTruthy();
  });

  it("asks for the next page by its offset when the operator wants more", async () => {
    answer([ROW], 2);
    renderUi(<VerificationQueue />);
    const more = await screen.findByRole("button", { name: "Show more (1 left)" });
    GET.mockClear();
    more.click();
    await waitFor(() => expect(GET).toHaveBeenCalled());
    const query = (GET.mock.calls[0][1] as { params: { query: { offset: number } } }).params.query;
    expect(query.offset).toBe(1);
  });

  it("has no button when the whole queue is on screen", async () => {
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/1 organisation waiting/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();
  });

  it("gives each organisation's link a 44 px target (Sprint 73): a queue of 100 is 100 of them", async () => {
    renderUi(<VerificationQueue />);
    const link = (await screen.findAllByRole("link"))[0];
    expect(link.className).toMatch(/min-h-11/);
  });
});

/** Sprint 89, BL-19.19: the kind of organisation is a word with a shape. */
describe("the verification queue -- the kind of organisation", () => {
  it("draws an employer and a provider as different words, shapes and tones", async () => {
    answer([ROW, { ...ROW, slug: "nsdc", name: "NSDC Healthcare Academy", tenant_type: "course_provider" }]);
    renderUi(<VerificationQueue />);
    const hiring = (await screen.findByText("Hiring", { selector: "span" })) as HTMLElement;
    const training = screen.getByText("Training", { selector: "span" }) as HTMLElement;
    expect(hiring.querySelector("svg")).toBeTruthy();
    expect(training.querySelector("svg")).toBeTruthy();
    expect(hiring.querySelector("svg")!.innerHTML).not.toBe(training.querySelector("svg")!.innerHTML);
    expect(hiring.className).toContain("bg-accent-soft");
    expect(training.className).toContain("bg-surface-muted");
  });
});

type Query = { q?: string; kind?: string; offset?: number };
const lastQuery = () => (GET.mock.calls.at(-1)![1] as { params: { query: Query } }).params.query;

/** Sprint 93, BL-22.8: a queue of hundreds is found by name and by kind, not by scrolling. */
describe("the verification queue -- search and kind", () => {
  it("has the filter row before the rows arrive, so nothing moves when they do", async () => {
    GET.mockImplementation(() => new Promise(() => {})); // never answers
    renderUi(<VerificationQueue />);
    expect(screen.getByRole("searchbox", { name: "Search the queue" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Kind of organisation" })).toBeTruthy();
  });

  it("asks the server for what was typed, and says how many match", async () => {
    answer([ROW], 162);
    renderUi(<VerificationQueue />);
    await screen.findByText(/Showing 1 of 162 organisations waiting/);
    answer([ROW], 3);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the queue" }), {
      target: { value: "apollo" },
    });
    // The filtered count is the server's, and it is a count of matches, not of the whole queue.
    expect(await screen.findByText(/Showing 1 of 3 that match/)).toBeTruthy();
    expect(lastQuery().q).toBe("apollo");
    expect(lastQuery().offset).toBe(0);
  });

  it("narrows to one kind, and sends nothing for 'all kinds'", async () => {
    renderUi(<VerificationQueue />);
    await screen.findByText("Apollo Care Hospitals");
    expect(lastQuery().kind).toBeUndefined();
    answer([{ ...ROW, tenant_type: "course_provider" }], 1);
    fireEvent.change(screen.getByRole("combobox", { name: "Kind of organisation" }), {
      target: { value: "course_provider" },
    });
    await waitFor(() => expect(lastQuery().kind).toBe("course_provider"));
    expect(await screen.findByText(/1 organisation matches/)).toBeTruthy();
  });

  it("says that nothing matches, which is not the same as an answered queue", async () => {
    renderUi(<VerificationQueue />);
    await screen.findByText("Apollo Care Hospitals");
    answer([], 0);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the queue" }), {
      target: { value: "zzz" },
    });
    expect(await screen.findByText("No organisation waiting matches that.")).toBeTruthy();
    expect(screen.queryByText(/Every organisation has been decided on/)).toBeNull();
  });

  it("clears both filters and asks for the whole queue again", async () => {
    renderUi(<VerificationQueue />);
    await screen.findByText("Apollo Care Hospitals");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the queue" }), {
      target: { value: "apollo" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Clear" }));
    await waitFor(() => expect(lastQuery().q).toBeUndefined());
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("");
  });

  it("keeps the first page's rows on screen while the next search loads", async () => {
    renderUi(<VerificationQueue />);
    await screen.findByText("Apollo Care Hospitals");
    GET.mockImplementation(() => new Promise(() => {}));
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the queue" }), {
      target: { value: "apo" },
    });
    // Still the old rows, not a skeleton: one flash per keystroke would be worse than a stale line.
    await waitFor(() => expect(lastQuery().q).toBe("apo"));
    expect(screen.getByText("Apollo Care Hospitals")).toBeTruthy();
  });
});

/** Sprint 95, ADR-102: a training centre waits for its address to be checked. */
describe("the verification queue -- a training centre", () => {
  const CENTRE = {
    ...ROW,
    slug: "acme-hadapsar",
    name: "Hadapsar",
    tenant_type: "training_centre",
    city: null,
    website: null,
    jobs: 0,
    courses: 0,
    members: 0,
    parent_name: "Acme Training",
    parent_slug: "acme",
    address: "12 Main Road",
    district: "Pune",
    state: "Maharashtra",
  };

  it("shows whose it is and the address to be checked, and none of an organisation's activity", async () => {
    answer([CENTRE]);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/Centre of Acme Training/)).toBeTruthy();
    expect(screen.getByText(/12 Main Road, Pune, Maharashtra/)).toBeTruthy();
    expect(screen.queryByText(/vacancies/)).toBeNull();
    expect(screen.queryByText("No website given")).toBeNull();
    expect(screen.queryByText(/No city given/)).toBeNull();
  });

  it("is its own word, shape and tone, apart from an employer and a provider", async () => {
    answer([ROW, { ...ROW, slug: "p", name: "Provider Co", tenant_type: "course_provider" }, CENTRE]);
    renderUi(<VerificationQueue />);
    await screen.findByText(/Centre of Acme Training/);
    const chips = ["Hiring", "Training", "Centre"].map(
      (w) => screen.getByText(w, { selector: "span" }) as HTMLElement,
    );
    const shapes = new Set(chips.map((c) => c.querySelector("svg")!.innerHTML));
    expect(shapes.size).toBe(3);
    const tones = new Set(chips.map((c) => c.className));
    expect(tones.size).toBe(3);
  });

  it("can be asked for on its own", async () => {
    answer([CENTRE]);
    renderUi(<VerificationQueue />);
    await screen.findByText(/Centre of Acme Training/);
    GET.mockClear();
    const kind = screen.getByRole("combobox", { name: /Kind/i });
    fireEvent.change(kind, { target: { value: "training_centre" } });
    await waitFor(() => expect(GET).toHaveBeenCalled());
    const query = (GET.mock.calls[0][1] as { params: { query: { kind?: string } } }).params.query;
    expect(query.kind).toBe("training_centre");
  });
});
