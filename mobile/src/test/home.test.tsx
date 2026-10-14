import { fireEvent, screen } from "@testing-library/react-native";

// `../../app` alone would resolve to app.json.
import Home from "../../app/index";
import { renderScreen } from "./harness";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
}));

let mockSignedIn = false;
let mockLocale: "en" | "hi" = "en";
const mockApi = { GET: jest.fn(), POST: jest.fn() };
const mockSetLocale = jest.fn();
const mockClear = jest.fn(async () => undefined);
// Looked up lazily: the factory runs at import time, before the `const`s above exist.
jest.mock("../runtime", () => ({
  api: {
    GET: (...args: unknown[]) => mockApi.GET(...args),
    POST: (...args: unknown[]) => mockApi.POST(...args),
  },
  tokens: { refresh: () => "r", clear: () => mockClear() },
  useLocale: () => mockLocale,
  setLocale: (...args: unknown[]) => mockSetLocale(...args),
  useSignedIn: () => mockSignedIn,
  useUpgradeRequired: () => null,
}));

const me = (kinds: ("personal" | "employer")[]) => ({
  data: {
    id: "u1",
    is_staff: false,
    memberships: kinds.map((tenant_type) => ({ role: "owner", tenant: { tenant_type, name: "x" } })),
  },
  error: undefined,
  response: { status: 200, headers: new Headers() },
});

beforeEach(() => {
  jest.clearAllMocks();
  mockSignedIn = false;
  mockLocale = "en";
  mockApi.GET.mockResolvedValue(me(["personal"]));
  mockApi.POST.mockResolvedValue({ data: undefined, error: undefined, response: { status: 204 } });
});

describe("the home screen", () => {
  it("offers sign-in to somebody signed out, and asks the API nothing", async () => {
    await renderScreen(<Home />);
    expect(screen.getByText("Find work that fits your skills")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Sign in" }));
    expect(mockPush).toHaveBeenCalledWith("/sign-in");
    // The web's rule: a signed-out visitor makes no request that can only answer 401.
    expect(mockApi.GET).not.toHaveBeenCalled();
  });

  it("says a job seeker is signed in and offers to sign out", async () => {
    mockSignedIn = true;
    await renderScreen(<Home />);
    expect(await screen.findByText("You are signed in.")).toBeTruthy();
    expect(screen.queryByText(/This app is for job seekers/)).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "Sign out" }));
    expect(mockApi.POST).toHaveBeenCalledWith("/auth/logout", { body: { refresh_token: "r" } });
    expect(mockClear).toHaveBeenCalled();
  });

  it("tells an organisation account that this app is for job seekers", async () => {
    mockSignedIn = true;
    mockApi.GET.mockResolvedValue(me(["employer"]));
    await renderScreen(<Home />);
    expect(await screen.findByText(/This app is for job seekers/)).toBeTruthy();
  });

  it("does not tell somebody who holds both a profile and an organisation to leave", async () => {
    mockSignedIn = true;
    mockApi.GET.mockResolvedValue(me(["personal", "employer"]));
    await renderScreen(<Home />);
    await screen.findByText("You are signed in.");
    expect(screen.queryByText(/This app is for job seekers/)).toBeNull();
  });

  it("changes the language when asked", async () => {
    await renderScreen(<Home />);
    await fireEvent.press(screen.getByRole("button", { name: "हिन्दी" }));
    expect(mockSetLocale).toHaveBeenCalledWith("hi");
  });
});
