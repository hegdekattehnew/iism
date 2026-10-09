import axe from "axe-core";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BulkUpload, MAX_FILE_BYTES } from "@/components/employer/BulkUpload";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
  },
}));

/**
 * The upload screen's three acts -- check, apply, publish -- and what stands between
 * them. Each of these fails on a screen that compiles and renders: a file written
 * before it was reviewed, drafts published without a second look, a refusal
 * reported as the wrong reason.
 */
const row = (over: Record<string, unknown> = {}) => ({
  row: 2,
  status: "ok",
  title: "Phlebotomist",
  external_ref: null,
  messages: [],
  standards: [
    { code: "HC/N0001", name: "Collect blood samples", origin: "listed" },
    { code: "HC/N0002", name: "Maintain a sterile field", origin: "role" },
  ],
  slug: null,
  created: false,
  ...over,
});

const report = (over: Record<string, unknown> = {}) => ({
  kind: "jobs",
  applied: false,
  rows: [row()],
  notes: [],
  ok: 1,
  warnings: 0,
  errors: 0,
  skipped: 0,
  created: 0,
  updates: 0,
  updating_live: 0,
  updated: 0,
  daily_limit: 100,
  remaining_today: 100,
  errors_csv: null,
  ...over,
});

const ok = (data: unknown) => ({
  data,
  error: undefined,
  response: { status: 200 },
});
const refused = (status: number, detail: string) => ({
  data: undefined,
  error: { detail },
  response: { status },
});

const upload = (content = "title\nPhlebotomist\n", name = "vacancies.csv") => {
  const input = screen.getByLabelText(/Your CSV file/);
  const file = new File([content], name, { type: "text/csv" });
  fireEvent.change(input, { target: { files: [file] } });
};

const screenFor = (kind: "jobs" | "courses" = "jobs") =>
  renderUi(<BulkUpload kind={kind} org="apollo-care" />);

const posted = (step: string) =>
  POST.mock.calls.filter((c) => String(c[0]).endsWith(`/${step}`));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});

describe("BulkUpload", () => {
  it("checks the file as raw CSV and writes nothing until asked", async () => {
    POST.mockResolvedValue(ok(report()));
    screenFor();
    upload("title\nPhlebotomist\n");

    expect(await screen.findByText("Phlebotomist")).toBeTruthy();
    expect(posted("check")).toHaveLength(1);
    const [path, options] = POST.mock.calls[0];
    expect(path).toBe("/org/{org_slug}/jobs/bulk/check");
    expect(options.body).toBe("title\nPhlebotomist\n");
    expect(options.headers["content-type"]).toBe("text/csv");
    // Not JSON-encoded: the serializer hands the text through untouched.
    expect(options.bodySerializer("abc")).toBe("abc");
    expect(posted("apply")).toHaveLength(0);
    expect(screen.getByText(/Nothing has been saved yet/)).toBeTruthy();
  });

  it("shows which standards a job role expanded to, and where each came from", async () => {
    POST.mockResolvedValue(ok(report()));
    screenFor();
    upload();
    expect(await screen.findByText("2 standards")).toBeTruthy();
    expect(screen.getByText("HC/N0002")).toBeTruthy();
    expect(screen.getByText(/from the job role/)).toBeTruthy();
  });

  it("will not create drafts from a file with problems until they are acknowledged", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          rows: [
            row(),
            row({ row: 3, status: "error", messages: ["title: too short"] }),
          ],
          ok: 1,
          errors: 1,
          errors_csv: "title,error\nx,title: too short\n",
        }),
      ),
    );
    screenFor();
    upload();

    const create = (await screen.findByRole("button", {
      name: "Create 1 drafts",
    })) as HTMLButtonElement;
    expect(create.disabled).toBe(true);
    expect(screen.getByText("title: too short")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /rows with a problem will be skipped/,
      }),
    );
    expect(create.disabled).toBe(false);
  });

  it("offers the rows to fix as a CSV download", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          errors: 1,
          errors_csv: "title,error\nx,bad\n",
          rows: [row({ status: "error" })],
        }),
      ),
    );
    screenFor();
    upload();
    fireEvent.click(
      await screen.findByRole("button", { name: "Download the rows to fix" }),
    );
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
  });

  it("creates drafts, then publishes only after a second, explicit confirmation", async () => {
    POST.mockImplementation(async (path: string) => {
      if (path.endsWith("/check")) return ok(report());
      if (path.endsWith("/apply"))
        return ok(
          report({
            applied: true,
            created: 1,
            rows: [row({ created: true, slug: "phlebotomist" })],
          }),
        );
      return ok({
        results: [{ slug: "phlebotomist", published: true, message: null }],
        published: 1,
        refused: 0,
      });
    });
    screenFor();
    upload();
    fireEvent.click(
      await screen.findByRole("button", { name: "Create 1 drafts" }),
    );

    expect(await screen.findByText("1 drafts created.")).toBeTruthy();
    expect(posted("publish")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Publish these 1" }));
    // Asked once more, with the consequence in words, before anything is public.
    expect(screen.getByText(/visible to everyone straight away/)).toBeTruthy();
    expect(posted("publish")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Yes, publish" }));
    await waitFor(() => expect(posted("publish")).toHaveLength(1));
    expect(posted("publish")[0][1].body).toEqual({ slugs: ["phlebotomist"] });
    expect(
      await screen.findByText("1 published, 0 not published."),
    ).toBeTruthy();
  });

  it("names a vacancy the server refused to publish, and why", async () => {
    POST.mockImplementation(async (path: string) => {
      if (path.endsWith("/check")) return ok(report());
      if (path.endsWith("/apply"))
        return ok(
          report({
            applied: true,
            created: 1,
            rows: [row({ created: true, slug: "no-standards" })],
          }),
        );
      return ok({
        results: [
          {
            slug: "no-standards",
            published: false,
            message: "Add at least one required standard before publishing",
          },
        ],
        published: 0,
        refused: 1,
      });
    });
    screenFor();
    upload();
    fireEvent.click(
      await screen.findByRole("button", { name: "Create 1 drafts" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Publish these 1" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, publish" }));
    expect(
      await screen.findByText(/Add at least one required standard/),
    ).toBeTruthy();
  });

  it("says what the server said, not a fixed sentence", async () => {
    POST.mockResolvedValue(
      refused(413, "That file has 300 rows; the limit is 200 per upload."),
    );
    screenFor();
    upload();
    expect(await screen.findByText(/300 rows; the limit is 200/)).toBeTruthy();
  });

  it("says a signed-out person is signed out, not that the file was wrong", async () => {
    POST.mockResolvedValue(refused(401, "Not authenticated"));
    screenFor();
    upload();
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
  });

  it("refuses a file over the size limit without sending it", async () => {
    screenFor();
    upload("x".repeat(MAX_FILE_BYTES + 1));
    expect(await screen.findByText(/larger than 2 MB/)).toBeTruthy();
    expect(POST).not.toHaveBeenCalled();
  });

  it("talks to the course endpoints for a provider", async () => {
    POST.mockResolvedValue(ok(report({ kind: "courses" })));
    screenFor("courses");
    expect(screen.getByText("Upload courses from a spreadsheet")).toBeTruthy();
    upload();
    await screen.findByText("Phlebotomist");
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/courses/bulk/check");
  });

  it("downloads the template the API serves", async () => {
    GET.mockResolvedValue({
      data: "title,description\n",
      error: undefined,
      response: { status: 200 },
    });
    screenFor();
    fireEvent.click(
      screen.getByRole("button", { name: "Download the template" }),
    );
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1));
    expect(GET.mock.calls[0][0]).toBe("/org/{org_slug}/jobs/bulk/template");
  });

  it("asks to update only when told to, and says so to the server in the query", async () => {
    POST.mockResolvedValue(ok(report()));
    screenFor();
    upload();
    await screen.findByText("Phlebotomist");
    expect(POST.mock.calls[0][1].params.query).toEqual({ existing: "skip" });
  });

  it("sends existing=update once the box is ticked, and re-checks a file already chosen", async () => {
    POST.mockResolvedValue(ok(report()));
    screenFor();
    upload();
    await screen.findByText("Phlebotomist");
    expect(posted("check")).toHaveLength(1);

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /Also update listings I uploaded before/,
      }),
    );

    // The old review is gone and the same file is checked again with the new choice: a stale
    // review must never sit beside a button that now does something else.
    await waitFor(() => expect(posted("check")).toHaveLength(2));
    expect(posted("check")[1][1].params.query).toEqual({ existing: "update" });
    expect(posted("check")[1][1].body).toBe("title\nPhlebotomist\n");
  });

  it("will not update live listings until that is acknowledged, and says how many", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          rows: [
            row({
              status: "update",
              slug: "ward-chennai",
              live: true,
              messages: ["will update ward-chennai (live): title"],
            }),
          ],
          ok: 0,
          updates: 1,
          updating_live: 1,
        }),
      ),
    );
    screenFor();
    upload();

    const go = (await screen.findByRole("button", {
      name: "Update 1",
    })) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    expect(screen.getByText(/1 of these is live/)).toBeTruthy();

    fireEvent.click(screen.getByRole("checkbox", { name: /of these is live/ }));
    expect(go.disabled).toBe(false);
  });

  it("names both halves when a file creates and updates", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          rows: [
            row(),
            row({ row: 3, status: "update", slug: "x", live: false }),
          ],
          ok: 1,
          updates: 1,
          updating_live: 0,
        }),
      ),
    );
    screenFor();
    upload();
    expect(
      await screen.findByRole("button", {
        name: "Create 1 drafts and update 1",
      }),
    ).toBeTruthy();
  });

  it("reports how many listings were updated after the apply", async () => {
    POST.mockImplementation(async (path: string) => {
      if (path.endsWith("/check"))
        return ok(
          report({
            ok: 0,
            updates: 1,
            rows: [row({ status: "update", slug: "x", live: false })],
          }),
        );
      return ok(
        report({
          applied: true,
          ok: 0,
          updates: 1,
          updated: 1,
          rows: [row({ status: "update", slug: "x", updated: true })],
        }),
      );
    });
    screenFor();
    upload();
    fireEvent.click(await screen.findByRole("button", { name: "Update 1" }));
    expect(await screen.findByText("1 listing updated.")).toBeTruthy();
    // Nothing was created, so there is nothing to publish and no publish step to offer.
    expect(screen.queryByRole("button", { name: /Publish these/ })).toBeNull();
  });

  it("is accessible with a review on screen, problems included", async () => {
    POST.mockResolvedValue(
      ok(
        report({
          rows: [
            row(),
            row({
              row: 3,
              status: "warning",
              messages: ["district not recognised"],
            }),
          ],
          ok: 1,
          warnings: 1,
          errors: 1,
          errors_csv: "title,error\nx,bad\n",
        }),
      ),
    );
    const { container } = screenFor();
    upload();
    await screen.findByText("district not recognised");
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
