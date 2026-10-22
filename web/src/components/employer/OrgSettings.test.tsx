import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrgSettings } from "@/components/employer/OrgSettings";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), PUT: (...a: unknown[]) => PUT(...a), POST: vi.fn() },
}));

const PROVIDER = {
  slug: "nsdc-academy",
  name: "NSDC Academy",
  tenant_type: "course_provider",
  city: "Pune",
  description: "We train ward staff.",
  website: null,
  logo_url: null,
  contact_email: "hello@nsdc.example",
  is_verified: false,
  publishes_courses: true,
  delivers_training: false,
  year_established: 2005,
  affiliations: "NSDC partner",
  teaching_languages: "Hindi",
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  PUT.mockReset();
});

function serve(org: Record<string, unknown>) {
  GET.mockResolvedValue({ data: org, error: undefined, response: { status: 200 } });
  PUT.mockImplementation(async (_path: string, init: { body: Record<string, unknown> }) => ({
    data: { ...org, ...init.body },
    error: undefined,
    response: { status: 200 },
  }));
}

/** Sprint 94, ADR-102: a training organisation's settings carry what it says about itself and what it does. */
describe("OrgSettings for a training organisation", () => {
  it("shows the three claims, the public page and what the organisation does", async () => {
    serve(PROVIDER);
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    expect(await screen.findByLabelText("Year established")).toHaveProperty("value", "2005");
    expect(screen.getByLabelText("Languages it teaches in")).toHaveProperty("value", "Hindi");
    expect(screen.getByLabelText("Affiliations")).toHaveProperty("value", "NSDC partner");
    expect(screen.getByRole("link", { name: "View your public page" }).getAttribute("href")).toBe(
      "/providers/nsdc-academy",
    );
    expect(screen.getByRole("group", { name: "What does your organisation do?" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: /Sells courses/ })).toHaveProperty("checked", true);
  });

  it("has two Save buttons that can be told apart by name", async () => {
    serve(PROVIDER);
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    await screen.findByLabelText("Year established");
    expect(screen.getByRole("button", { name: "Save" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save what it does" })).toBeTruthy();
  });

  it("saves the claims, the year as a number and a blank as nothing", async () => {
    serve(PROVIDER);
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    const year = await screen.findByLabelText("Year established");
    fireEvent.change(year, { target: { value: "1998" } });
    fireEvent.change(screen.getByLabelText("Affiliations"), { target: { value: "  " } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(PUT).toHaveBeenCalled());
    const body = (PUT.mock.calls[0][1] as { body: Record<string, unknown> }).body;
    expect(body.year_established).toBe(1998);
    expect(body.affiliations).toBeNull();
    expect(body.teaching_languages).toBe("Hindi");
  });

  it("sends no year at all as null rather than zero", async () => {
    serve({ ...PROVIDER, year_established: null });
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    await screen.findByLabelText("Year established");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(PUT).toHaveBeenCalled());
    expect((PUT.mock.calls[0][1] as { body: Record<string, unknown> }).body.year_established).toBeNull();
  });
});

describe("OrgSettings for an employer", () => {
  it("has none of that: no claims, no public page, nothing about training", async () => {
    serve({ ...PROVIDER, tenant_type: "employer", publishes_courses: false, year_established: null });
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    await screen.findByLabelText("Organisation name");
    expect(screen.queryByLabelText("Year established")).toBeNull();
    expect(screen.queryByLabelText("Affiliations")).toBeNull();
    expect(screen.queryByRole("link", { name: "View your public page" })).toBeNull();
    expect(screen.queryByRole("group", { name: "What does your organisation do?" })).toBeNull();
  });

  it("saves without sending the claims it never showed", async () => {
    serve({ ...PROVIDER, tenant_type: "employer", publishes_courses: false });
    renderUi(<OrgSettings orgSlug="nsdc-academy" />);
    await screen.findByLabelText("Organisation name");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(PUT).toHaveBeenCalled());
    const body = (PUT.mock.calls[0][1] as { body: Record<string, unknown> }).body;
    expect("year_established" in body).toBe(false);
    expect("affiliations" in body).toBe(false);
  });
});
