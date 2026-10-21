import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContactForm } from "@/components/ContactForm";
import { GrievanceForm } from "@/components/GrievanceForm";
import { GRIEVANCE_LOOK } from "@/components/cards/grievance-look";
import { renderUi, resetWorld, world } from "@/test/harness";

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
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * The two public forms (Sprint 57, BL-14.3). What varies is who is signed in: a stranger must
 * leave somewhere to reply and may not ask about data; a signed-in person gives nothing and may.
 * `tsc` cannot see a branch that picks the wrong actor.
 */

const MESSAGE =
  "My employer shared my number outside the vacancy I applied to.";
const SENT = {
  reference: "GRV-ABC234",
  kind: "grievance",
  acknowledge_within_hours: 24,
  resolve_within_days: 15,
};

function ok(over: Record<string, unknown> = {}) {
  POST.mockResolvedValue({
    data: { ...SENT, ...over },
    error: undefined,
    response: { status: 201, headers: new Headers() },
  });
}

function refuse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
) {
  POST.mockResolvedValue({
    data: undefined,
    error: body,
    response: { status, headers: new Headers(headers) },
  });
}

const type = (label: RegExp | string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({
    data: [],
    error: undefined,
    response: { status: 200 },
  });
  ok();
});

describe("the contact form", () => {
  it("asks a stranger where to reply, and sends nothing until they have said", async () => {
    world.signedIn = false;
    renderUi(<ContactForm />);
    const send = screen.getByRole("button", {
      name: "Send",
    }) as HTMLButtonElement;

    type(/^Your message/, MESSAGE);
    expect(send.disabled).toBe(true);

    type(/^Where can we reply\?/, "ravi@example.org");
    expect(send.disabled).toBe(false);
  });

  it("does not ask a signed-in person for an address, and sends none", async () => {
    renderUi(<ContactForm />);
    expect(screen.queryByLabelText(/^Where can we reply\?/)).toBeNull();

    type(/^Your message/, MESSAGE);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    const body = POST.mock.calls[0][1].body;
    expect(body.reply_to).toBeUndefined();
    expect(body.kind).toBe("contact");
  });

  it("will not send a message shorter than the server's floor", () => {
    renderUi(<ContactForm />);
    type(/^Your message/, "too short");
    expect(
      (screen.getByRole("button", { name: "Send" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("leaves the honeypot empty for a person, out of the tab order and out of sight", async () => {
    world.signedIn = false;
    renderUi(<ContactForm />);
    const trap = document.querySelector(
      'input[name="website"]',
    ) as HTMLInputElement;
    expect(trap.tabIndex).toBe(-1);
    expect(trap.closest('[aria-hidden="true"]')).not.toBeNull();

    type(/^Your message/, MESSAGE);
    type(/^Where can we reply\?/, "ravi@example.org");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][1].body.website).toBe("");
  });

  it("shows the reference and what to expect, and a signed-out sender is told nobody emails them", async () => {
    world.signedIn = false;
    ok({ kind: "contact" });
    renderUi(<ContactForm />);
    type(/^Your message/, MESSAGE);
    type(/^Where can we reply\?/, "ravi@example.org");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect((await screen.findByTestId("grievance-reference")).textContent).toBe(
      "GRV-ABC234",
    );
    expect(screen.getByText(/never send anything automatically/)).toBeTruthy();
    expect(screen.queryByText(/within 24 hours/)).toBeNull(); // a note promises no deadline
  });

  it("says what the server said when it refuses", async () => {
    refuse(422, {
      detail: "Give an email address or a mobile number we can write back to.",
    });
    renderUi(<ContactForm />);
    type(/^Your message/, MESSAGE);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(
      await screen.findByText(
        "Give an email address or a mobile number we can write back to.",
      ),
    ).toBeTruthy();
  });

  it("counts down a 429 from the number the server gave and keeps the button off", async () => {
    refuse(429, { detail: "Too many messages." }, { "retry-after": "90" });
    renderUi(<ContactForm />);
    type(/^Your message/, MESSAGE);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(/Try again in 90 seconds/)).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Send" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
});

describe("the grievance form", () => {
  it("sends a complaint with the promise on screen afterwards", async () => {
    renderUi(<GrievanceForm />);
    type(/^Your message/, MESSAGE);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(
      await screen.findByText(
        /within 24 hours and aim to resolve it within 15 days/,
      ),
    ).toBeTruthy();
    expect(POST.mock.calls[0][1].body.kind).toBe("grievance");
  });

  it("sends a signed-out person who picks a data request to sign in, with no form to fill", () => {
    world.signedIn = false;
    renderUi(<GrievanceForm />);
    fireEvent.click(screen.getByLabelText(/A request about my data/));

    expect(screen.getByText(/has to come from your account/)).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Sign in" }).getAttribute("href"),
    ).toBe("/signin");
    expect(screen.queryByLabelText(/^Your message/)).toBeNull();
    expect(POST).not.toHaveBeenCalled();
  });

  it("lets a signed-in person make a data request", async () => {
    renderUi(<GrievanceForm />);
    fireEvent.click(screen.getByLabelText(/A request about my data/));
    type(
      /^Your message/,
      "Please send me a copy of everything you hold about me.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][1].body.kind).toBe("data_request");
  });

  it("lists a signed-in person's own messages and where each stands, never an operator's note", async () => {
    GET.mockResolvedValue({
      data: [
        {
          reference: "GRV-AAA111",
          kind: "grievance",
          status: "resolved",
          created_at: "2026-09-01T08:00:00Z",
          acknowledged_at: "2026-09-01T10:00:00Z",
          resolved_at: "2026-09-05T08:00:00Z",
        },
        {
          reference: "GRV-BBB222",
          kind: "contact",
          status: "open",
          created_at: "2026-10-01T08:00:00Z",
        },
      ],
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<GrievanceForm />);
    expect(await screen.findByText("GRV-AAA111")).toBeTruthy();
    expect(screen.getByText("Resolved")).toBeTruthy();
    expect(screen.getByText("GRV-BBB222")).toBeTruthy();
    expect(screen.getByText("Received")).toBeTruthy();
  });

  it("shows a signed-out visitor no list of messages and makes no request for one", () => {
    world.signedIn = false;
    renderUi(<GrievanceForm />);
    expect(
      screen.queryByRole("heading", { name: "What you have sent" }),
    ).toBeNull();
    expect(GET).not.toHaveBeenCalled();
  });
});

/** Sprint 89, BL-19.19/19.20: the kind chooser's rows are 44 px, and what a person has sent has a shape per status. */
describe("the grievance form -- targets and the person's own list", () => {
  it("makes each kind a 44 px row with a 20 px radio", () => {
    renderUi(<GrievanceForm />);
    for (const radio of screen.getAllByRole("radio")) {
      expect((radio.closest("label") as HTMLElement).className).toContain("min-h-11");
      expect(radio.className).toContain("h-5 w-5");
    }
  });

  it.each([
    ["open", "Received", "bg-warning-surface"],
    ["acknowledged", "Being looked at", "bg-accent-soft"],
    ["resolved", "Resolved", "bg-success-surface"],
    ["dismissed", "Closed", "bg-surface-muted"],
  ])("draws a message that is %s as %s on %s, with a shape", async (status, word, token) => {
    GET.mockResolvedValue({
      data: [{ reference: "GRV-ABC234", kind: "grievance", status, created_at: "2026-10-01T08:00:00Z", acknowledged_at: null, resolved_at: null }],
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<GrievanceForm />);
    const chip = (await screen.findByText(word, { selector: "span" })) as HTMLElement;
    expect(chip.className).toContain(token);
    expect(chip.querySelector("svg")).toBeTruthy();
  });

  it("draws each status in the shape its look names, and the four are four different shapes", async () => {
    const shapes: string[] = [];
    for (const [status, word] of [["open", "Received"], ["acknowledged", "Being looked at"], ["resolved", "Resolved"], ["dismissed", "Closed"]] as const) {
      GET.mockResolvedValue({
        data: [{ reference: "GRV-ABC234", kind: "grievance", status, created_at: "2026-10-01T08:00:00Z", acknowledged_at: null, resolved_at: null }],
        error: undefined,
        response: { status: 200 },
      });
      const { unmount } = renderUi(<GrievanceForm />);
      const chip = (await screen.findByText(word, { selector: "span" })) as HTMLElement;
      const Icon = GRIEVANCE_LOOK[status].icon;
      const expected = render(<Icon />).container.querySelector("svg")!.innerHTML;
      expect(chip.querySelector("svg")!.innerHTML).toBe(expected);
      shapes.push(expected);
      unmount();
    }
    expect(new Set(shapes).size).toBe(4);
  });
});
