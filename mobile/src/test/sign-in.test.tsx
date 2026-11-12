import { fireEvent, screen, waitFor } from "@testing-library/react-native";

import SignIn from "../../app/sign-in";
import appHi from "../messages/app.hi.json";
import hi from "../messages/hi.json";
import { renderScreen } from "./harness";

const mockReplace = jest.fn();
jest.mock("expo-router", () => ({
  useRouter: () => ({ replace: mockReplace, push: jest.fn() }),
}));

const mockApi = { GET: jest.fn(), POST: jest.fn() };
const mockTokens = {
  access: jest.fn(() => null),
  refresh: jest.fn(() => null),
  set: jest.fn(async (_tokens: unknown) => undefined),
  clear: jest.fn(async () => undefined),
};
// The factory runs when the screen first imports `../runtime`, which is before the `const`s above
// are initialised (imports are hoisted), so every use goes through a function that looks them up
// later.
jest.mock("../runtime", () => ({
  api: {
    GET: (...args: unknown[]) => mockApi.GET(...args),
    POST: (...args: unknown[]) => mockApi.POST(...args),
  },
  tokens: {
    access: () => mockTokens.access(),
    refresh: () => mockTokens.refresh(),
    set: (tokens: unknown) => mockTokens.set(tokens),
    clear: () => mockTokens.clear(),
  },
  useLocale: () => "en",
  setLocale: jest.fn(),
  useSignedIn: () => false,
  useUpgradeRequired: () => null,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200, headers: new Headers() } });
const refused = (status: number, detail: string, headers: Record<string, string> = {}) => ({
  data: undefined,
  error: { detail },
  response: { status, headers: new Headers(headers) },
});

const SENT = { sent: true, expires_in_seconds: 300, resend_after_seconds: 30, debug_code: "123456" };
const SIGNED_IN = { access_token: "a", refresh_token: "r", token_type: "bearer", expires_in: 900, created: false };

beforeEach(() => {
  jest.clearAllMocks();
  mockApi.POST.mockImplementation(async (path: string) =>
    path === "/auth/otp/request" ? ok(SENT) : ok(SIGNED_IN),
  );
});

async function toCodeStep() {
  await fireEvent.changeText(screen.getByLabelText("Mobile number"), "9810000001");
  await fireEvent.press(screen.getByRole("button", { name: "Send code" }));
  await screen.findByText("Enter the code");
}

describe("the sign-in screen", () => {
  it("will not send a code for a number that is too short", async () => {
    await renderScreen(<SignIn />);
    expect(screen.getByRole("button", { name: "Send code" })).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Mobile number"), "98100");
    expect(screen.getByRole("button", { name: "Send code" })).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Mobile number"), "9810000001");
    expect(screen.getByRole("button", { name: "Send code" })).toBeEnabled();
  });

  it("asks for a code and moves to the code step, showing the development code", async () => {
    await renderScreen(<SignIn />);
    await toCodeStep();
    expect(mockApi.POST).toHaveBeenCalledWith("/auth/otp/request", { body: { phone: "9810000001" } });
    expect(screen.getByText("Development mode: your code is 123456")).toBeTruthy();
  });

  it("counts down the server's cooldown before another code may be asked for", async () => {
    await renderScreen(<SignIn />);
    await toCodeStep();
    const resend = screen.getByRole("button", { name: /Send a new code in \d+s/ });
    expect(resend).toBeDisabled();
  });

  it("verifies the code, stores the session and goes home", async () => {
    await renderScreen(<SignIn />);
    await toCodeStep();
    await fireEvent.changeText(screen.getByLabelText("6-digit code"), "123456");
    await fireEvent.press(screen.getByRole("button", { name: "Verify and continue" }));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/"));
    expect(mockTokens.set).toHaveBeenCalledWith({ access_token: "a", refresh_token: "r" });
  });

  it("sends no consent until the box is ticked, then sends the notice version", async () => {
    await renderScreen(<SignIn />);
    await toCodeStep();
    await fireEvent.changeText(screen.getByLabelText("6-digit code"), "123456");
    await fireEvent.press(screen.getByRole("button", { name: "Verify and continue" }));
    await waitFor(() => expect(mockReplace).toHaveBeenCalled());
    const first = mockApi.POST.mock.calls.find((c) => c[0] === "/auth/otp/verify")![1];
    expect(first.body).toEqual({ phone: "9810000001", code: "123456" });

    mockApi.POST.mockClear();
    mockReplace.mockClear();
    await fireEvent(screen.getByLabelText(/I have read the privacy notice/), "valueChange", true);
    await fireEvent.press(screen.getByRole("button", { name: "Verify and continue" }));
    await waitFor(() => expect(mockReplace).toHaveBeenCalled());
    const second = mockApi.POST.mock.calls.find((c) => c[0] === "/auth/otp/verify")![1];
    expect(second.body).toEqual({ phone: "9810000001", code: "123456", consent_version: "2026-10-24" });
  });

  it("says what to do when the number has no account yet, and stores nothing", async () => {
    mockApi.POST.mockImplementation(async (path: string) =>
      path === "/auth/otp/request" ? ok(SENT) : refused(428, "consent_required"),
    );
    await renderScreen(<SignIn />);
    await toCodeStep();
    await fireEvent.changeText(screen.getByLabelText("6-digit code"), "123456");
    await fireEvent.press(screen.getByRole("button", { name: "Verify and continue" }));
    expect(await screen.findByText(/Tick the box to agree to the privacy notice/)).toBeTruthy();
    expect(mockTokens.set).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("says a wrong code is wrong", async () => {
    mockApi.POST.mockImplementation(async (path: string) =>
      path === "/auth/otp/request" ? ok(SENT) : refused(401, "Incorrect or expired code"),
    );
    await renderScreen(<SignIn />);
    await toCodeStep();
    await fireEvent.changeText(screen.getByLabelText("6-digit code"), "000000");
    await fireEvent.press(screen.getByRole("button", { name: "Verify and continue" }));
    expect(await screen.findByText("That code is incorrect or has expired.")).toBeTruthy();
  });

  it("tells somebody who asked too soon how long to wait", async () => {
    mockApi.POST.mockResolvedValue(refused(429, "Slow down", { "retry-after": "17" }));
    await renderScreen(<SignIn />);
    await fireEvent.changeText(screen.getByLabelText("Mobile number"), "9810000001");
    await fireEvent.press(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByText(/Please wait 17 seconds/)).toBeTruthy();
  });

  it("speaks Hindi from the web's own catalogue", async () => {
    await renderScreen(<SignIn />, "hi");
    expect(screen.getByText(hi.auth.signInTitle)).toBeTruthy();
    expect(screen.getByLabelText(appHi.signIn.phoneLabel)).toBeTruthy();
  });
});
