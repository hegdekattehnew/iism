import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { Text as NativeText } from "react-native";

import { dark, light } from "../theme/tokens";
import { useColours } from "../theme";
import { themePreference } from "../theme/preference";
import { AppearanceChooser } from "../ui/AppearanceChooser";

import { renderScreen } from "./harness";

// The runtime is replaced by hand in every screen test; the chooser needs only the setter, and a
// factory runs before this file's own constants exist, so it looks the store up when called.
jest.mock("../runtime", () => ({
  setThemePreference: (value: "system" | "light" | "dark") =>
    (jest.requireActual("../theme/preference") as typeof import("../theme/preference")).themePreference.set(value),
}));

let mockScheme: "light" | "dark" = "light";
jest.mock("react-native/Libraries/Utilities/useColorScheme", () => ({ __esModule: true, default: () => mockScheme }));

beforeEach(() => {
  mockScheme = "light";
  themePreference.set("light");
});

function Probe() {
  const c = useColours();
  return <NativeText testID="probe">{c.background}</NativeText>;
}

describe("the appearance chooser", () => {
  it("offers light, dark and the phone's own setting, with light selected", async () => {
    await renderScreen(<AppearanceChooser />);
    expect(screen.getByRole("button", { name: "Light" }).props.accessibilityState).toMatchObject({ selected: true });
    expect(screen.getByRole("button", { name: "Match phone" }).props.accessibilityState).toMatchObject({ selected: false });
    expect(screen.getByRole("button", { name: "Dark" }).props.accessibilityState).toMatchObject({ selected: false });
  });

  it("choosing dark selects it and stores it", async () => {
    await renderScreen(<AppearanceChooser />);
    await fireEvent.press(screen.getByRole("button", { name: "Dark" }));
    expect(themePreference.get()).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark" }).props.accessibilityState).toMatchObject({ selected: true });
    expect(screen.getByRole("button", { name: "Match phone" }).props.accessibilityState).toMatchObject({ selected: false });
  });
});

describe("the colours follow the choice, then the phone", () => {
  it("with no choice it is light, even on a phone that is in dark mode", async () => {
    mockScheme = "dark";
    await render(<Probe />);
    expect(screen.getByTestId("probe").props.children).toBe(light.background);
  });

  it("matching the phone follows it", async () => {
    await act(async () => themePreference.set("system"));
    await render(<Probe />);
    expect(screen.getByTestId("probe").props.children).toBe(light.background);
    mockScheme = "dark";
    await render(<Probe />);
    expect(screen.getAllByTestId("probe").at(-1)!.props.children).toBe(dark.background);
  });

  it("a choice wins over the phone, either way", async () => {
    await render(<Probe />);
    await act(async () => themePreference.set("dark"));
    expect(screen.getByTestId("probe").props.children).toBe(dark.background);
    mockScheme = "dark";
    await act(async () => themePreference.set("light"));
    expect(screen.getByTestId("probe").props.children).toBe(light.background);
  });
});
