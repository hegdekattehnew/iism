import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InterestPanel } from "@/components/InterestPanel";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    DELETE: vi.fn(),
  },
}));

/**
 * The learner's half of Sprint 24's disclosure. Who is offered the button, and
 * what they are told before they press it.
 */

const panel = () => (
  <InterestPanel courseSlug="phlebotomy-refresher" organisation="SkillBridge Institute" />
);

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({ data: [], error: undefined });
  POST.mockResolvedValue({
    data: { id: "i1", status: "registered" },
    error: undefined,
    response: { status: 201 },
  });
});

describe("InterestPanel — who is offered the button", () => {
  it("asks a signed-out visitor to sign in, rather than failing later", () => {
    world.signedIn = false;
    renderUi(panel());
    expect(
      screen.getByRole("link", { name: "Sign in to register interest" }).getAttribute("href"),
    ).toBe("/signin");
  });

  it("offers a job seeker the button", async () => {
    world.memberships = [personal()];
    renderUi(panel());
    expect(
      await screen.findByRole("button", { name: "I'm interested in this course" }),
    ).toBeTruthy();
  });

  it("offers an organisation-only account nothing at all", () => {
    // `get_current_candidate` refuses this account, so a button here would be
    // an affordance that always fails.
    world.memberships = [org("nsdc", "course_provider")];
    const { container } = renderUi(panel());
    expect(screen.queryByRole("button")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("renders nothing while it does not yet know which kind of account this is", () => {
    world.pending = true;
    const { container } = renderUi(panel());
    expect(container.textContent).toBe("");
  });
});

describe("InterestPanel — the consent moment", () => {
  beforeEach(() => {
    world.memberships = [personal()];
  });

  it("names the provider and what they will see, before anything is shared", async () => {
    renderUi(panel());
    fireEvent.click(
      await screen.findByRole("button", { name: "I'm interested in this course" }),
    );

    const confirm = await screen.findByText(/SkillBridge Institute will see/);
    expect(confirm.textContent).toContain("phone number");
    expect(screen.getByText(/You can withdraw at any time/)).toBeTruthy();
    // Nothing is sent until the second, explicit press.
    expect(POST).not.toHaveBeenCalled();
  });

  it("sends the note with the registration", async () => {
    renderUi(panel());
    fireEvent.click(
      await screen.findByRole("button", { name: "I'm interested in this course" }),
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Evenings only" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/me/course-interests");
    expect(init.body).toEqual({
      course_slug: "phlebotomy-refresher",
      message: "Evenings only",
    });
  });

  it("offers withdrawal once registered, and not the register button", async () => {
    GET.mockResolvedValue({
      data: [
        {
          id: "i1",
          status: "registered",
          course: { slug: "phlebotomy-refresher", title: "Phlebotomy Refresher" },
        },
      ],
      error: undefined,
    });
    renderUi(panel());

    expect(await screen.findByText("Interest registered")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw" })).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "I'm interested in this course" }),
    ).toBeNull();
  });

  it("offers the button again after a withdrawal", async () => {
    GET.mockResolvedValue({
      data: [
        {
          id: "i1",
          status: "withdrawn",
          course: { slug: "phlebotomy-refresher", title: "Phlebotomy Refresher" },
        },
      ],
      error: undefined,
    });
    renderUi(panel());
    expect(
      await screen.findByRole("button", { name: "I'm interested in this course" }),
    ).toBeTruthy();
  });

  it("says what went wrong rather than sitting there", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "x" },
      response: { status: 409 },
    });
    renderUi(panel());
    fireEvent.click(
      await screen.findByRole("button", { name: "I'm interested in this course" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));

    expect(
      await screen.findByText("You have already registered interest in this course."),
    ).toBeTruthy();
  });
});
