import { fireEvent, screen, waitFor } from"@testing-library/react";
import { beforeEach, describe, expect, it, vi } from"vitest";

import { CreateOrgForm } from"@/components/CreateOrgForm";
import { renderUi, resetWorld } from"@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { POST: (...a: unknown[]) => POST(...a), GET: vi.fn(), DELETE: vi.fn() },
}));

/**
 * The regression test for Sprint 26's dialog bug.
 *
 * The defect was a **containing block**, not a style: `Header` carries
 * `backdrop-blur`, an ancestor with `backdrop-filter` becomes the containing
 * block for `position: fixed` descendants, and this form rendered its own
 * `fixed inset-0` overlay from inside that header. It resolved to the header's
 * 64px-tall box instead of the viewport.
 *
 * **jsdom has no layout**, so measuring a rect here would prove nothing — every
 * rect is 0×0. What jsdom *can* prove is the thing that actually caused it:
 * where in the tree the dialog is mounted. If it is a descendant of `<header>`
 * again, the bug is back. The measurement belongs in a real browser and is in
 * the sprint's verification steps.
 */

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  POST.mockResolvedValue({ data: { slug: "new-org" }, error: undefined });
});

const form = () => <CreateOrgForm onClose={() => {}} onCreated={() => {}} />;

describe("CreateOrgForm — where it renders", () => {
  it("escapes the element it is mounted inside", () => {
    // The real tree is Header → ContextSwitcher → CreateOrgForm, and the
    // header is what carried `backdrop-filter`. Reproduced here as an
    // explicit wrapper, because rendering the form as a *sibling* of the
    // header proves nothing: it would pass whether or not the dialog
    // portals, which is how the first version of this test was vacuous.
    renderUi(
      <div data-testid="blurred-ancestor">
        {form()}
      </div>,
    );

    const dialog = screen.getByRole("dialog");
    const ancestor = screen.getByTestId("blurred-ancestor");
    expect(ancestor.contains(dialog)).toBe(false);
    expect(dialog.closest("header")).toBeNull();
  });

  it("portals out to the document, not into the render container", () => {
    // Radix renders to document.body. Asserting on `container` rather than
    // `screen` is also how a portalled dialog silently"disappears" from a
    // test that queries the wrong root.
    const { container } = renderUi(form());
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});

describe("CreateOrgForm — the modal contract it never had", () => {
  it("moves focus into the dialog", async () => {
    renderUi(form());
    const dialog = screen.getByRole("dialog");
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    renderUi(<CreateOrgForm onClose={onClose} onCreated={() => {}} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("names itself, so it is not an unlabelled modal", () => {
    renderUi(form());
    expect(screen.getByRole("dialog", { name: "Create an organisation" })).toBeTruthy();
  });
});

describe("CreateOrgForm — what it sends", () => {
  it("posts to /me/organisations, which adds a membership not an account", async () => {
    // The whole reason this component exists: `/auth/org/register` would mint
    // a second `User` for an unfamiliar address (ADR-038).
    renderUi(form());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Apollo Care" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/me/organisations");
    expect(init.body).toEqual({ organisation_name: "Apollo Care", tenant_type: "employer" });
  });

  it("says what went wrong rather than sitting there", async () => {
    POST.mockResolvedValue({ data: undefined, error: { detail: "x" } });
    renderUi(form());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Apollo Care" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
