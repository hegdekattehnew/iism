import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SignUpTypeSwitch } from "@/components/SignUpTypeSwitch";
import { renderUi } from "@/test/harness";

vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const link = (name: string) => screen.getByRole("link", { name });

describe("SignUpTypeSwitch — registration is for all three, from any door", () => {
  it("offers employer and provider registration from the job-seeker page", () => {
    // The reported bug: /signup/seeker offered phone registration and nothing
    // else, and the only way to an organisation account was the Back button.
    renderUi(<SignUpTypeSwitch current="seeker" />);

    expect(link("Hire").getAttribute("href")).toBe("/signup/employer");
    expect(link("Offer training").getAttribute("href")).toBe("/signup/provider");
    expect(link("Find work").getAttribute("href")).toBe("/signup/seeker");
  });

  it("marks exactly the type the page is for as current", () => {
    renderUi(<SignUpTypeSwitch current="provider" />);

    expect(link("Offer training").getAttribute("aria-current")).toBe("page");
    expect(link("Find work").getAttribute("aria-current")).toBeNull();
    expect(link("Hire").getAttribute("aria-current")).toBeNull();
  });

  it("is labelled as a choice of what you are here to do", () => {
    renderUi(<SignUpTypeSwitch current="employer" />);

    expect(screen.getByRole("navigation", { name: "I'm here to…" })).toBeTruthy();
  });
});
