import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DistrictSkillGap } from "@/components/ops/DistrictSkillGap";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

const DISTRICT = { id: "d-1", name: "Gap Town", state: "Gap State", vacancies: 2 };

function serve(standards: unknown[], residents: number | null = 9) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/ops/districts") return ok({ districts: [DISTRICT] });
    if (path === "/ops/districts/{district_id}/skill-gap") {
      return ok({
        district: DISTRICT,
        positions: 11,
        residents,
        residents_below_minimum: residents === null,
        minimum_cell: 5,
        standards,
      });
    }
    return ok(undefined);
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("DistrictSkillGap", () => {
  it("says so when no district has an open vacancy, rather than an empty picker", async () => {
    GET.mockImplementation(async () => ok({ districts: [] }));
    renderUi(<DistrictSkillGap />);
    expect(await screen.findByText("No district has an open vacancy yet.")).toBeTruthy();
  });

  it("names its picker: a placeholder option is not an accessible name", async () => {
    // axe `select-name`, found on /admin by Sprint 53's route sweep: the only text was the
    // "Choose a district" option, which a screen reader does not announce as the control's label.
    serve([]);
    renderUi(<DistrictSkillGap />);
    expect(await screen.findByRole("combobox", { name: "District skill gap" })).toBeTruthy();
  });

  it("never prints a count the server withheld, and marks the shortfall beside it a minimum", async () => {
    serve([
      {
        nos_code: "GAP/N1",
        name: "Alpha",
        vacancies: 2,
        demand: 11,
        supply: 6,
        supply_below_minimum: false,
        shortfall: 5,
        shortfall_is_minimum: false,
      },
      {
        nos_code: "GAP/N2",
        name: "Bravo",
        vacancies: 1,
        demand: 9,
        supply: null,
        supply_below_minimum: true,
        shortfall: 5,
        shortfall_is_minimum: true,
      },
    ]);
    renderUi(<DistrictSkillGap />);
    const picker = await screen.findByRole("combobox");
    fireEvent.change(picker, { target: { value: "d-1" } });

    expect(await screen.findByText("Bravo")).toBeTruthy();
    // The hidden row reads "fewer than 5" and "at least 5" -- not a number of residents.
    expect(screen.getByText("fewer than 5")).toBeTruthy();
    expect(screen.getByText("at least 5")).toBeTruthy();
    // The exact row shows its own supply as a plain number.
    expect(screen.getByText("6")).toBeTruthy();
    expect(screen.getByText(/A count of fewer than 5 residents is not shown/)).toBeTruthy();
  });

  it("hides the resident total the same way", async () => {
    serve([], null);
    renderUi(<DistrictSkillGap />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "d-1" } });
    await waitFor(() =>
      expect(screen.getByText(/Fewer than 5 residents with a declared standard/)).toBeTruthy(),
    );
    expect(screen.getByText("No open vacancy in this district asks for a standard yet.")).toBeTruthy();
  });

  it("says the district could not be loaded when the request fails", async () => {
    GET.mockImplementation(async (path: string) => {
      if (path === "/ops/districts") return ok({ districts: [DISTRICT] });
      return { data: undefined, error: { detail: "boom" }, response: { status: 500 } };
    });
    renderUi(<DistrictSkillGap />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "d-1" } });
    expect(await screen.findByText("That district could not be loaded.")).toBeTruthy();
  });
});
