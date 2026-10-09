import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProgrammeDashboard } from "@/components/ops/ProgrammeDashboard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("ProgrammeDashboard", () => {
  it("says so when no programme has enrolled anyone yet, rather than an empty picker", async () => {
    GET.mockImplementation(async (path: string) => {
      if (path === "/ops/programmes") {
        return { data: { programmes: [] }, error: undefined, response: { status: 200 } };
      }
      return { data: undefined, error: undefined, response: { status: 200 } };
    });
    renderUi(<ProgrammeDashboard />);
    expect(await screen.findByText("No programme has enrolled anyone yet.")).toBeTruthy();
  });

  it("names its picker: a placeholder option is not an accessible name", async () => {
    // axe `select-name`, found on /admin by Sprint 53's route sweep.
    GET.mockImplementation(async (path: string) => {
      if (path === "/ops/programmes") {
        return { data: { programmes: ["PMKVY-TEST"] }, error: undefined, response: { status: 200 } };
      }
      return { data: undefined, error: undefined, response: { status: 200 } };
    });
    renderUi(<ProgrammeDashboard />);
    expect(await screen.findByRole("combobox", { name: "Programme outcomes" })).toBeTruthy();
  });

  it("renders the chosen programme's outcomes once one is picked", async () => {
    GET.mockImplementation(async (path: string, opts?: { params?: { path?: { name?: string } } }) => {
      if (path === "/ops/programmes") {
        return {
          data: { programmes: ["PMKVY-TEST"] },
          error: undefined,
          response: { status: 200 },
        };
      }
      if (path === "/ops/programmes/{name}" && opts?.params?.path?.name === "PMKVY-TEST") {
        return {
          data: { programme: "PMKVY-TEST", enrolled: 12, matched: 7, applied: 5, hired: 2 },
          error: undefined,
          response: { status: 200 },
        };
      }
      if (
        path === "/ops/programmes/{name}/districts" &&
        opts?.params?.path?.name === "PMKVY-TEST"
      ) {
        return {
          data: {
            programme: "PMKVY-TEST",
            districts: [{ district: "Nagpur", enrolled: 9 }],
          },
          error: undefined,
          response: { status: 200 },
        };
      }
      return { data: undefined, error: undefined, response: { status: 200 } };
    });
    const { getByRole } = renderUi(<ProgrammeDashboard />);
    const select = await screen.findByRole("combobox");
    (select as HTMLSelectElement).value = "PMKVY-TEST";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => expect(screen.getByText("12")).toBeTruthy());
    expect(screen.getByText("7")).toBeTruthy();
    expect(getByRole("combobox")).toBeTruthy();
    expect(await screen.findByText("Nagpur")).toBeTruthy();
    expect(screen.getByText("9")).toBeTruthy();
  });

  it("writes a count the server withheld as 'fewer than 5' and never as a number", async () => {
    GET.mockImplementation(async (path: string) => {
      if (path === "/ops/programmes") {
        return { data: { programmes: ["P"] }, error: undefined, response: { status: 200 } };
      }
      if (path === "/ops/programmes/{name}") {
        return {
          data: { programme: "P", enrolled: 13, matched: 1, applied: 1, hired: 0 },
          error: undefined,
          response: { status: 200 },
        };
      }
      if (path === "/ops/programmes/{name}/districts") {
        return {
          data: {
            programme: "P",
            minimum_cell: 5,
            districts: [
              { district: "Nagpur", enrolled: 9, below_minimum: false },
              { district: "Tiny Town", enrolled: null, below_minimum: true },
            ],
          },
          error: undefined,
          response: { status: 200 },
        };
      }
      return { data: undefined, error: undefined, response: { status: 200 } };
    });
    renderUi(<ProgrammeDashboard />);
    const select = await screen.findByRole("combobox");
    (select as HTMLSelectElement).value = "P";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    expect(await screen.findByText("Tiny Town")).toBeTruthy();
    expect(screen.getByText("fewer than 5")).toBeTruthy();
    expect(screen.getByText("9")).toBeTruthy();
    expect(screen.getByText(/A count of fewer than 5 is not shown/)).toBeTruthy();
  });
});
