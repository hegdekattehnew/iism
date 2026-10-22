import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CentresUpload } from "@/components/employer/CentresUpload";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const row = (over: Record<string, unknown> = {}) => ({
  row: 2,
  status: "ok",
  name: "Hadapsar",
  messages: [],
  slug: null,
  created: false,
  ...over,
});
const report = (over: Record<string, unknown> = {}) => ({
  applied: false,
  rows: [row()],
  notes: [],
  ok: 1,
  warnings: 0,
  errors: 0,
  skipped: 0,
  created: 0,
  remaining: 199,
  errors_csv: null,
  ...over,
});
const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

const choose = (text = "name,state,district\nHadapsar,Maharashtra,Pune\n") => {
  const input = screen.getByLabelText("A CSV file, up to 2 MB") as HTMLInputElement;
  const file = new File([text], "centres.csv", { type: "text/csv" });
  fireEvent.change(input, { target: { files: [file] } });
};

/** Sprint 95: a file of centres is checked first and added only when the person says so. */
describe("CentresUpload", () => {
  it("checks the file as soon as it is chosen and writes nothing", async () => {
    POST.mockResolvedValue(ok(report()));
    renderUi(<CentresUpload org="acme" />);
    choose();
    await screen.findByText("1 ready, 0 to look at, 0 with a problem, 0 already there.");
    expect(POST).toHaveBeenCalledTimes(1);
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/centres/bulk/check");
    expect(screen.getByRole("button", { name: "Add 1 centre" })).toBeTruthy();
  });

  it("adds only when asked, to the apply route, with the same file", async () => {
    POST.mockResolvedValueOnce(ok(report())).mockResolvedValueOnce(
      ok(report({ applied: true, created: 1, rows: [row({ created: true, slug: "acme-hadapsar" })] })),
    );
    renderUi(<CentresUpload org="acme" />);
    choose("name,state,district\nHadapsar,Maharashtra,Pune\n");
    fireEvent.click(await screen.findByRole("button", { name: "Add 1 centre" }));
    await screen.findByText("1 centre added.");
    expect(POST.mock.calls[1][0]).toBe("/org/{org_slug}/centres/bulk/apply");
    expect((POST.mock.calls[1][1] as { body: string }).body).toContain("Hadapsar");
  });

  it("holds the button until the person has acknowledged the rows that will not be added", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          ok: 1,
          errors: 1,
          rows: [row(), row({ row: 3, status: "error", name: "X", messages: ["name: must have at least 2 characters"] })],
          errors_csv: "name,error\r\nX,bad\r\n",
        }),
      ),
    );
    renderUi(<CentresUpload org="acme" />);
    choose();
    const button = await screen.findByRole("button", { name: "Add 1 centre" });
    expect(button).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(button).toHaveProperty("disabled", false));
    expect(screen.getByRole("button", { name: "Download the rows to fix" })).toBeTruthy();
  });

  it("will not add anything from a file whose every row has a problem, even when acknowledged", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          ok: 0,
          errors: 1,
          rows: [row({ status: "error", messages: ["name: must have at least 2 characters"] })],
        }),
      ),
    );
    renderUi(<CentresUpload org="acme" />);
    choose();
    fireEvent.click(await screen.findByRole("checkbox"));
    const button = screen.getByRole("button", { name: "Add 0 centres" });
    expect(button).toHaveProperty("disabled", true);
  });

  it("shows each row's result as a word, so a long file is not read by colour", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          ok: 1,
          warnings: 1,
          skipped: 1,
          rows: [
            row(),
            row({ row: 3, status: "warning", name: "Lost", messages: ["The place was not found"] }),
            row({ row: 4, status: "skip", name: "Old", messages: ["already"] }),
          ],
        }),
      ),
    );
    renderUi(<CentresUpload org="acme" />);
    choose();
    await screen.findByText("Lost");
    for (const word of ["Ready", "Warning", "Skipped"]) {
      expect(screen.getByText(word, { selector: "span" }).querySelector("svg")).toBeTruthy();
    }
  });

  it("gives the server's own sentence when it refuses the file", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "The file is not UTF-8." },
      response: { status: 422 },
    });
    renderUi(<CentresUpload org="acme" />);
    choose();
    expect((await screen.findByRole("alert")).textContent).toContain("not UTF-8");
  });
});
