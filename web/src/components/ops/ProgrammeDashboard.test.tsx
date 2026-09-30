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
      return { data: undefined, error: undefined, response: { status: 200 } };
    });
    const { getByRole } = renderUi(<ProgrammeDashboard />);
    const select = await screen.findByRole("combobox");
    (select as HTMLSelectElement).value = "PMKVY-TEST";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => expect(screen.getByText("12")).toBeTruthy());
    expect(screen.getByText("7")).toBeTruthy();
    expect(getByRole("combobox")).toBeTruthy();
  });
});
