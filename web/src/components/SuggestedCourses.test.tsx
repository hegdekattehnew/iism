import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CourseBudgetControl,
  SuggestedCourses,
} from "@/components/SuggestedCourses";
import type { components } from "@/lib/api-schema";
import { setCourseBudget, useCourseBudget } from "@/lib/course-budget";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

type Suggestion = components["schemas"]["CourseSuggestionOut"];

const base: Suggestion = {
  slug: "gda",
  title: "General duty assistant",
  mode: "offline",
  language: "both",
  duration_hours: 320,
  fee_inr: 12000,
  closes: ["Infection control"],
  closes_count: 1,
  gap_size: 3,
  covers_mandatory: 1,
  location_state: "Maharashtra",
  location_district: "Pune",
  starts_on: "2026-12-01",
  seats_left: 7,
  reach: "district",
  started: false,
  full: false,
  within_budget: null,
  attendable: true,
};

beforeEach(() => {
  resetWorld();
  window.localStorage.clear();
  act(() => setCourseBudget(null));
});

describe("a suggested course says where, when, what it costs and whether there is room", () => {
  it("shows the place, the intake, the fee and the seats left", () => {
    renderUi(<SuggestedCourses courses={[base]} />);
    expect(screen.getByText(/Pune, Maharashtra/)).toBeTruthy();
    expect(screen.getByText(/Starts Dec 1, 2026/)).toBeTruthy();
    expect(screen.getByText(/₹12,000/)).toBeTruthy();
    expect(screen.getByText(/7 seats left/)).toBeTruthy();
    expect(screen.getByText("In your district")).toBeTruthy();
    expect(screen.getByText("Closes 1 of 3 of your gap")).toBeTruthy();
  });

  it("does not invent a place for an online course", () => {
    renderUi(
      <SuggestedCourses
        courses={[
          {
            ...base,
            mode: "online",
            location_state: null,
            location_district: null,
            reach: "online",
          },
        ]}
      />,
    );
    expect(screen.queryByText(/not stated/i)).toBeNull();
    expect(screen.getAllByText("Online").length).toBeGreaterThan(0);
  });

  it("says plainly when an in-person course gave no place or no start date", () => {
    renderUi(
      <SuggestedCourses
        courses={[
          {
            ...base,
            location_state: null,
            location_district: null,
            starts_on: null,
            reach: "unknown",
          },
        ]}
      />,
    );
    expect(screen.getByText(/Place not stated/)).toBeTruthy();
    expect(screen.getByText(/Start date not stated/)).toBeTruthy();
    // No reach badge for an unknown place: nothing is claimed about the person.
    expect(screen.queryByText("In your district")).toBeNull();
    expect(screen.queryByText("Elsewhere")).toBeNull();
  });

  it("labels a course that is elsewhere, started, full or over budget, and hides none", () => {
    renderUi(
      <SuggestedCourses
        courses={[
          {
            ...base,
            reach: "elsewhere",
            started: true,
            full: true,
            seats_left: 0,
            within_budget: false,
            attendable: false,
            starts_on: "2026-01-05",
          },
        ]}
      />,
    );
    expect(screen.getByText("Elsewhere")).toBeTruthy();
    expect(screen.getByText("Already started")).toBeTruthy();
    expect(screen.getByText("Full")).toBeTruthy();
    expect(screen.getByText("Over your budget")).toBeTruthy();
    expect(screen.getByText(/Started Jan 5, 2026/)).toBeTruthy();
    expect(screen.queryByText(/seats left/)).toBeNull();
    expect(
      screen.getByRole("link", { name: "General duty assistant" }),
    ).toBeTruthy();
  });

  it("reads a free course as free", () => {
    renderUi(<SuggestedCourses courses={[{ ...base, fee_inr: null }]} />);
    expect(screen.getByText(/Free/)).toBeTruthy();
  });

  it("makes no claim about the person when there is no person (the employer's sponsor panel)", () => {
    renderUi(
      <SuggestedCourses
        forPerson={false}
        courses={[
          { ...base, reach: "elsewhere", within_budget: false, started: true },
        ]}
      />,
    );
    expect(screen.queryByText("Elsewhere")).toBeNull();
    expect(screen.queryByText("In your district")).toBeNull();
    expect(screen.queryByText("Over your budget")).toBeNull();
    // What is true of the course itself still shows.
    expect(screen.getByText("Already started")).toBeTruthy();
    expect(screen.getByText(/Pune, Maharashtra/)).toBeTruthy();
  });

  it("reports which course was opened", () => {
    const onOpen = vi.fn();
    renderUi(<SuggestedCourses courses={[base]} onOpen={onOpen} />);
    fireEvent.click(
      screen.getByRole("link", { name: "General duty assistant" }),
    );
    expect(onOpen).toHaveBeenCalledWith("gda");
  });
});

function Probe() {
  return <output data-testid="budget">{String(useCourseBudget())}</output>;
}

describe("the budget control", () => {
  const input = () =>
    screen.getByLabelText(/What would you pay/) as HTMLInputElement;

  it("is the field library's: labelled, 44 px, narrow, with the number's limits at the control (Sprint 87)", () => {
    renderUi(<CourseBudgetControl />);
    const box = input();
    expect(box.className).toContain("min-h-11");
    expect(box.className).toContain("w-36");
    expect(box.getAttribute("min")).toBe("0");
    expect(box.getAttribute("max")).toBe("10000000");
    expect(box.getAttribute("name")).toBe("budget_inr");
  });

  it("applies a number when the person leaves the field, not on every keystroke", async () => {
    renderUi(
      <>
        <CourseBudgetControl />
        <Probe />
      </>,
    );
    fireEvent.change(input(), { target: { value: "5000" } });
    expect(screen.getByTestId("budget").textContent).toBe("null");
    fireEvent.blur(input());
    await waitFor(() =>
      expect(screen.getByTestId("budget").textContent).toBe("5000"),
    );
    expect(window.localStorage.getItem("iism:course-budget")).toBe("5000");
  });

  it("applies on Enter, and clears with the button", async () => {
    renderUi(
      <>
        <CourseBudgetControl />
        <Probe />
      </>,
    );
    fireEvent.change(input(), { target: { value: "3000" } });
    fireEvent.submit(input().closest("form") as HTMLFormElement);
    await waitFor(() =>
      expect(screen.getByTestId("budget").textContent).toBe("3000"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() =>
      expect(screen.getByTestId("budget").textContent).toBe("null"),
    );
    expect(window.localStorage.getItem("iism:course-budget")).toBeNull();
  });

  it("refuses what the server would: a negative, a fraction, or more than the ceiling", async () => {
    renderUi(
      <>
        <CourseBudgetControl />
        <Probe />
      </>,
    );
    for (const bad of ["-5", "12.5", "10000001"]) {
      fireEvent.change(input(), { target: { value: bad } });
      fireEvent.blur(input());
    }
    expect(screen.getByTestId("budget").textContent).toBe("null");
  });

  it("still works for this visit when storage refuses", async () => {
    const set = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("blocked");
      });
    renderUi(
      <>
        <CourseBudgetControl />
        <Probe />
      </>,
    );
    fireEvent.change(input(), { target: { value: "800" } });
    fireEvent.blur(input());
    await waitFor(() =>
      expect(screen.getByTestId("budget").textContent).toBe("800"),
    );
    set.mockRestore();
  });
});
