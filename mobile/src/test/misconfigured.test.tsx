import { fireEvent, screen } from "@testing-library/react-native";
import { Linking } from "react-native";

import { Misconfigured } from "../screens/Misconfigured";
import { renderScreen } from "./harness";

describe("Misconfigured", () => {
  it("says what happened in plain words and offers the store", async () => {
    const open = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
    await renderScreen(<Misconfigured />);
    expect(screen.getByText("This copy of the app is not set up correctly")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Open the store" }));
    expect(open).toHaveBeenCalledTimes(1);
    open.mockRestore();
  });

  it("is in Hindi too", async () => {
    await renderScreen(<Misconfigured />, "hi");
    expect(screen.getByText("ऐप की यह प्रति ठीक से सेट नहीं है")).toBeTruthy();
  });

  it("names no technical reason (a person cannot act on one)", async () => {
    await renderScreen(<Misconfigured />);
    expect(screen.queryByText(/localhost|https?:|api-|cleartext/i)).toBeNull();
  });
});
