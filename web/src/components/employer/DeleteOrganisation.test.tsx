import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeleteOrganisation } from "@/components/employer/DeleteOrganisation";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const DELETE = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), DELETE: (...a: unknown[]) => DELETE(...a) },
}));

/**
 * The control that was missing when this was reported: a job seeker with two
 * organisations could only delete their whole account.
 */

const preview = (over: Record<string, unknown> = {}) => ({
  slug: "my-hiring-co",
  name: "My Hiring Co",
  tenant_type: "employer",
  jobs: 3,
  courses: 0,
  applications: 7,
  course_interests: 0,
  other_members: 0,
  ...over,
});

const panel = () => <DeleteOrganisation orgSlug="my-hiring-co" />;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  DELETE.mockReset();
  GET.mockResolvedValue({ data: preview(), error: undefined });
  DELETE.mockResolvedValue({ error: undefined });
});

describe("DeleteOrganisation — what it says before it does anything", () => {
  it("names the applications, which are the part an owner does not think of", async () => {
    renderUi(panel());
    expect(await screen.findByText(/7 applications/)).toBeTruthy();
    expect(screen.getByText(/3 vacancies/)).toBeTruthy();
  });

  it("says what survives, because not knowing that was the complaint", async () => {
    renderUi(panel());
    expect(
      await screen.findByText(/your other organisations are not affected/i),
    ).toBeTruthy();
  });

  it("does not mention other members when there are none", async () => {
    // A sole owner is not "1 other member loses access".
    renderUi(panel());
    await screen.findByText(/7 applications/);
    expect(screen.queryByText(/lose their access/)).toBeNull();
  });

  it("warns about other members when there are some", async () => {
    GET.mockResolvedValue({ data: preview({ other_members: 2 }), error: undefined });
    renderUi(panel());
    expect(await screen.findByText(/2 other members lose their access/)).toBeTruthy();
  });
});

describe("DeleteOrganisation — the confirmation", () => {
  it("keeps the button disabled until the name is typed exactly", async () => {
    renderUi(panel());
    const button = await screen.findByRole("button", { name: "Delete organisation" });
    expect(button).toHaveProperty("disabled", true);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "my hiring co" } });
    expect(button).toHaveProperty("disabled", true);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My Hiring Co" } });
    expect(button).toHaveProperty("disabled", false);
  });

  it("deletes only this organisation", async () => {
    renderUi(panel());
    await screen.findByRole("button", { name: "Delete organisation" });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My Hiring Co" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete organisation" }));

    await waitFor(() => expect(DELETE).toHaveBeenCalledTimes(1));
    const [path, init] = DELETE.mock.calls[0] as [string, { params: { path: object } }];
    expect(path).toBe("/org/{org_slug}");
    expect(init.params.path).toEqual({ org_slug: "my-hiring-co" });
  });

  it("says what went wrong rather than sitting there", async () => {
    DELETE.mockResolvedValue({ error: { detail: "x" } });
    renderUi(panel());
    await screen.findByRole("button", { name: "Delete organisation" });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My Hiring Co" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete organisation" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

describe("DeleteOrganisation — who sees it", () => {
  it("renders nothing for an admin, who is a member but not an owner", async () => {
    // A button that always fails is worse than no button (Sprint 14).
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "forbidden" },
      response: { status: 403 },
    });
    const { container } = renderUi(panel());
    await waitFor(() => expect(container.textContent).toBe(""));
  });

  it("tells a signed-out owner their session expired, rather than hiding", async () => {
    // **The reported bug.** An owner was told to scroll to the delete card and
    // found nothing there: their fifteen-minute token had expired half an hour
    // earlier, and 401 was being treated exactly like 403.
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderUi(panel());

    expect(await screen.findByText(/session has expired/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in again" }).getAttribute("href")).toBe(
      "/signin",
    );
  });
});
