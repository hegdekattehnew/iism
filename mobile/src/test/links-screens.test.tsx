import { fireEvent, screen } from "@testing-library/react-native";
import { Linking } from "react-native";

import Invite from "../../app/invite/[token]";
import { redirectSystemPath } from "../../app/+native-intent";
import { resetWorld, world } from "./mocks";
import { renderScreen } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

const open = jest.spyOn(Linking, "openURL");

beforeEach(() => {
  resetWorld();
  open.mockReset().mockResolvedValue(true as never);
});

describe("an invitation to an organisation", () => {
  it("says this app is for job seekers and hands the invitation to the browser, accepting nothing", async () => {
    world.params = { token: "AbCdEf12_-xyz" };
    await renderScreen(<Invite />);
    expect(screen.getByText("This invitation is for an organisation")).toBeTruthy();
    expect(screen.getByText(/This app is for job seekers/)).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Open in the browser" }));
    expect(open).toHaveBeenCalledWith("http://localhost:3000/en/invite/AbCdEf12_-xyz");
  });

  it("encodes a token so it cannot change the address it opens", async () => {
    world.params = { token: "a/../b?x=1" };
    await renderScreen(<Invite />);
    await fireEvent.press(screen.getByRole("button", { name: "Open in the browser" }));
    expect(open).toHaveBeenCalledWith("http://localhost:3000/en/invite/a%2F..%2Fb%3Fx%3D1");
  });
});

describe("a link that reaches the app from outside", () => {
  it("opens what it names", () => {
    expect(redirectSystemPath({ path: "iism://job/ward-assistant-1", initial: false })).toBe("/job/ward-assistant-1");
    expect(redirectSystemPath({ path: "/notifications", initial: true })).toBe("/notices");
  });

  it("opens Home for an unknown link that launched the app, and nothing for one that did not", () => {
    expect(redirectSystemPath({ path: "iism://admin", initial: true })).toBe("/");
    expect(redirectSystemPath({ path: "iism://admin", initial: false })).toBeNull();
    expect(redirectSystemPath({ path: "//evil.example", initial: false })).toBeNull();
  });

  it("never follows a website link from a host that is not ours", () => {
    expect(redirectSystemPath({ path: "https://evil.example/jobs/x", initial: false })).toBeNull();
  });
});
