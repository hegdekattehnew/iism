import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchesUpload } from "@/components/employer/BatchesUpload";
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
  course: "welding-basics",
  centre: "hadapsar",
  messages: [],
  id: null,
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
  errors_csv: null,
  ...over,
});
const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });
const refused = (status: number, detail: string) => ({
  data: undefined,
  error: { detail },
  response: { status },
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

const choose = (text = "course,centre,starts_on,ends_on,seats\nwelding-basics,hadapsar,2026-12-01,2027-01-01,25\n") => {
  const input = screen.getByLabelText("A CSV file, up to 2 MB") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File([text], "batches.csv", { type: "text/csv" })] } });
};

/** Sprint 99: a file of batches is checked, made into drafts, and published as its own act. */
describe("BatchesUpload", () => {
  it("checks the file as soon as it is chosen, to the check route, and writes nothing", async () => {
    POST.mockResolvedValue(ok(report()));
    renderUi(<BatchesUpload org="acme" />);
    choose();
    await screen.findByText("1 ready, 0 to look at, 0 with a problem, 0 already planned.");
    expect(POST).toHaveBeenCalledTimes(1);
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/batches/bulk/check");
    expect(screen.getByRole("button", { name: "Make 1 draft batch" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Publish/ })).toBeNull();
  });

  it("makes drafts only when asked, with the same file, and does not publish them", async () => {
    POST.mockResolvedValueOnce(ok(report())).mockResolvedValueOnce(
      ok(report({ applied: true, created: 1, rows: [row({ created: true, id: "b-1" })] })),
    );
    renderUi(<BatchesUpload org="acme" />);
    choose();
    fireEvent.click(await screen.findByRole("button", { name: "Make 1 draft batch" }));
    await screen.findByText("1 draft batch made.");
    expect(POST.mock.calls[1][0]).toBe("/org/{org_slug}/batches/bulk/apply");
    expect((POST.mock.calls[1][1] as { body: string }).body).toContain("welding-basics");
    expect(POST).toHaveBeenCalledTimes(2);
    expect(screen.getByText("4. Publish")).toBeTruthy();
  });

  it("publishes the ids the apply returned, after a confirmation, and says what was refused", async () => {
    POST.mockResolvedValueOnce(ok(report()))
      .mockResolvedValueOnce(
        ok(
          report({
            applied: true,
            created: 2,
            rows: [
              row({ created: true, id: "b-1" }),
              row({ row: 3, created: true, id: "b-2" }),
              // Already planned: the server names the batch it matched, and it is not ours to publish.
              row({ row: 4, status: "skip", id: "b-0", created: false }),
            ],
          }),
        ),
      )
      .mockResolvedValueOnce(
        ok({
          results: [
            { id: "b-1", published: true, message: null },
            { id: "b-2", published: false, message: "The first day has already passed." },
          ],
          published: 1,
          refused: 1,
        }),
      );
    renderUi(<BatchesUpload org="acme" />);
    choose();
    fireEvent.click(await screen.findByRole("button", { name: "Make 1 draft batch" }));
    fireEvent.click(await screen.findByRole("button", { name: "Publish these 2" }));
    expect(POST).toHaveBeenCalledTimes(2); // nothing published by the first press
    expect(screen.getByText("Publish 2 batches?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Yes, publish" }));
    await screen.findByText("1 published, 1 not published.");
    expect(POST.mock.calls[2][0]).toBe("/org/{org_slug}/batches/bulk/publish");
    expect((POST.mock.calls[2][1] as { body: { ids: string[] } }).body.ids).toEqual(["b-1", "b-2"]);
    expect(screen.getByText("The first day has already passed.")).toBeTruthy();
  });

  it("offers no publish step for a file that made nothing", async () => {
    POST.mockResolvedValueOnce(ok(report({ ok: 0, skipped: 1, rows: [row({ status: "skip" })] }))).mockResolvedValueOnce(
      ok(report({ applied: true, created: 0, ok: 0, skipped: 1, rows: [row({ status: "skip" })] })),
    );
    renderUi(<BatchesUpload org="acme" />);
    choose();
    await screen.findByText("0 ready, 0 to look at, 0 with a problem, 1 already planned.");
    expect((screen.getByRole("button", { name: "Make 0 draft batches" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("holds the button until the rows that will not be made are acknowledged, and offers them to fix", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          errors: 1,
          rows: [row(), row({ row: 3, status: "error", messages: ["No course you may deliver is called that."] })],
          errors_csv: "course,error\r\nnope,bad\r\n",
        }),
      ),
    );
    renderUi(<BatchesUpload org="acme" />);
    choose();
    const button = await screen.findByRole("button", { name: "Make 1 draft batch" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("No course you may deliver is called that.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download the rows to fix" })).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/1 row has a problem and will not be made/));
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the server's own words when the file is refused", async () => {
    POST.mockResolvedValue(refused(400, "The file has no data rows."));
    renderUi(<BatchesUpload org="acme" />);
    choose("course,centre\n");
    expect(await screen.findByText("The file has no data rows.")).toBeTruthy();
  });

  it("refuses a file over 2 MB before sending it", async () => {
    renderUi(<BatchesUpload org="acme" />);
    const big = new File(["x".repeat(2 * 1024 * 1024 + 10)], "big.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("A CSV file, up to 2 MB"), { target: { files: [big] } });
    expect(await screen.findByText(/larger than 2 MB/)).toBeTruthy();
    expect(POST).not.toHaveBeenCalled();
  });

  it("can start again with another file", async () => {
    POST.mockResolvedValue(ok(report()));
    renderUi(<BatchesUpload org="acme" />);
    choose();
    await screen.findByText(/1 ready/);
    fireEvent.click(screen.getByRole("button", { name: "Use another file" }));
    await waitFor(() => expect(screen.queryByText(/1 ready/)).toBeNull());
  });
});
