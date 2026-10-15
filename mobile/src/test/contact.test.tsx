import { fireEvent, screen } from "@testing-library/react-native";

import Contact from "../../app/contact";
import { account, api, failed, ok, resetWorld, serve, world } from "./mocks";
import { renderScreen } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const MESSAGE = "I would like to know how my data is used.";
const submitted = (kind = "contact") => ({ reference: "G-2026-0007", kind, acknowledge_within_hours: 24, resolve_within_days: 15 });
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));
const body = () => (api.POST.mock.calls[0][1] as { body: Record<string, unknown> }).body;

describe("writing to the team, signed out", () => {
  it("offers a question and a complaint, and no request about your own data", async () => {
    await renderScreen(<Contact />);
    expect(await screen.findByRole("button", { name: "A question or a note" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "A complaint" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "A request about my data" })).toBeNull();
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("cannot be sent without enough words and an address to answer at", async () => {
    await renderScreen(<Contact />);
    const send = await screen.findByRole("button", { name: "Send" });
    expect(send).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Your message"), MESSAGE);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Where can we reply?"), "asha@example.org");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("sends the message and the address, with the honeypot empty, and says what happens next", async () => {
    serve(api.POST, { "/grievances": ok(submitted("grievance")) });
    await renderScreen(<Contact />);
    await press("A complaint");
    await fireEvent.changeText(screen.getByLabelText("Your message"), `  ${MESSAGE}  `);
    await fireEvent.changeText(screen.getByLabelText("Where can we reply?"), " asha@example.org ");
    await press("Send");
    expect(await screen.findByText("We have your message")).toBeTruthy();
    expect(body()).toEqual({ kind: "grievance", body: MESSAGE, reply_to: "asha@example.org", website: "" });
    expect(screen.getByText("Your reference: G-2026-0007")).toBeTruthy();
    expect(screen.getByText(/We acknowledge it within 24 hours and aim to resolve it within 15 days/)).toBeTruthy();
    expect(screen.getByText(/We reply to the address you gave/)).toBeTruthy();
  });

  it("says how long to wait when it is asked to", async () => {
    serve(api.POST, { "/grievances": () => ({ data: undefined, error: { detail: "slow down" }, response: { status: 429, headers: new Headers({ "retry-after": "42" }) } }) });
    await renderScreen(<Contact />);
    await fireEvent.changeText(screen.getByLabelText("Your message"), MESSAGE);
    await fireEvent.changeText(screen.getByLabelText("Where can we reply?"), "asha@example.org");
    await press("Send");
    expect(await screen.findByText(/Try again in 42 seconds/)).toBeTruthy();
  });

  it("shows the server's own sentence when it refuses a field", async () => {
    serve(api.POST, { "/grievances": failed(422, "Give an email address or a ten-digit mobile number to write back to.") });
    await renderScreen(<Contact />);
    await fireEvent.changeText(screen.getByLabelText("Your message"), MESSAGE);
    await fireEvent.changeText(screen.getByLabelText("Where can we reply?"), "nonsense");
    await press("Send");
    expect(await screen.findByText(/Give an email address or a ten-digit mobile number/)).toBeTruthy();
  });

  it("mirrors the server's limits on the inputs", async () => {
    await renderScreen(<Contact />);
    expect((await screen.findByLabelText("Your message")).props.maxLength).toBe(4000);
    expect(screen.getByLabelText("Where can we reply?").props.maxLength).toBe(254);
  });
});

describe("writing to the team, signed in", () => {
  beforeEach(() => {
    world.signedIn = true;
  });

  it("offers a request about your own data, asks for no address and sends none", async () => {
    serve(api.GET, { "/auth/me": ok(account()), "/me/grievances": ok([]) });
    serve(api.POST, { "/grievances": ok(submitted("data_request")) });
    await renderScreen(<Contact />);
    await press("A request about my data");
    expect(screen.queryByLabelText("Where can we reply?")).toBeNull();
    await fireEvent.changeText(screen.getByLabelText("Your message"), MESSAGE);
    await press("Send");
    await screen.findByText("We have your message");
    expect(body()).toEqual({ kind: "data_request", body: MESSAGE, website: "" });
    expect(screen.getByText(/You will see where it stands on this page and in your updates/)).toBeTruthy();
  });

  it("shows what was sent before and where each stands, and never an operator's note", async () => {
    serve(api.GET, {
      "/auth/me": ok(account()),
      "/me/grievances": ok([
        { reference: "G-1", kind: "grievance", status: "acknowledged", created_at: "2026-10-14T20:00:00+00:00", resolved_at: null, operator_note: "SECRET NOTE" },
        { reference: "G-2", kind: "contact", status: "resolved", created_at: "2026-10-01T10:00:00+00:00", resolved_at: "2026-10-05T10:00:00+00:00" },
      ]),
    });
    await renderScreen(<Contact />);
    expect(await screen.findByText("G-1")).toBeTruthy();
    expect(screen.getByText("Being looked at")).toBeTruthy();
    expect(screen.getByText("Resolved")).toBeTruthy();
    expect(screen.getByText("Sent 15 Oct 2026")).toBeTruthy();
    expect(screen.getByText("Sent 1 Oct 2026 · closed 5 Oct 2026")).toBeTruthy();
    expect(screen.queryByText(/SECRET NOTE/)).toBeNull();
  });
});
