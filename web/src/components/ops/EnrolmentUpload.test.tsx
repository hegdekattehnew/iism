import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EnrolmentUpload } from "@/components/ops/EnrolmentUpload";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);
const saveCsv = vi.fn();
vi.mock("@/lib/download", () => ({
  saveCsv: (...a: unknown[]) => saveCsv(...a),
}));

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

const SIGNED_OUT = "Your session has expired. Sign in again to continue.";

const ok = (data: unknown) => ({
  data,
  error: undefined,
  response: { status: 200 },
});

const REPORT = (applied: boolean) => ({
  programme: "PMKVY-2026",
  applied,
  rows: [
    {
      row: 2,
      status: "new",
      phone: "+9198*****001",
      first_name: "Anita",
      warnings: [],
      errors: [],
    },
    {
      row: 3,
      status: "error",
      phone: null,
      first_name: "Ravi",
      warnings: [],
      errors: [
        "phone: not an Indian mobile number (ten digits starting 6 to 9)",
      ],
    },
    {
      row: 4,
      status: "tag",
      phone: "+9198*****003",
      first_name: "Meena",
      warnings: [],
      errors: [],
    },
  ],
  notes: [],
  new: 1,
  tag: 1,
  already: 0,
  errors: 1,
  errors_csv: "phone,full_name,error\r\n123,Ravi,bad\r\n",
  batch_id: applied ? "11111111-1111-1111-1111-111111111111" : null,
});

const BATCH = {
  id: "22222222-2222-2222-2222-222222222222",
  programme: "OLDER-PROGRAMME",
  file_name: "older.csv",
  operator: "op****@example.com",
  attested_notice_version: "2026-09",
  attested_at: "2026-10-01T09:00:00Z",
  created: 5,
  tagged: 1,
  already: 0,
  errors: 0,
  created_at: "2026-10-01T09:00:00Z",
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  saveCsv.mockReset();
  GET.mockImplementation(async (path: string) => {
    if (path === "/ops/programmes")
      return ok({ programmes: ["OLDER-PROGRAMME"] });
    if (path === "/ops/enrolment/batches") return ok({ batches: [BATCH] });
    if (path === "/ops/enrolment/template")
      return { data: "phone,full_name\r\n", response: { status: 200 } };
    return ok({});
  });
  POST.mockImplementation(async (path: string) =>
    ok(REPORT(path === "/ops/enrolment/apply")),
  );
});

const choose = async (
  name = "agency.csv",
  body = "phone\r\n9810000001\r\n",
) => {
  const input = (await screen.findByLabelText(
    "Choose the CSV file",
  )) as HTMLInputElement;
  const file = new File([body], name, { type: "text/csv" });
  Object.defineProperty(file, "text", { value: () => Promise.resolve(body) });
  fireEvent.change(input, { target: { files: [file] } });
  await screen.findByText(name);
};

const name = async (value: string) => {
  fireEvent.change(await screen.findByLabelText("Programme name"), {
    target: { value },
  });
};

describe("the enrolment upload", () => {
  it("is absent for a support operator, not a disabled panel", async () => {
    world.staffTier = "support";
    renderUi(<EnrolmentUpload />);
    await waitFor(() =>
      expect(GET).not.toHaveBeenCalledWith(
        "/ops/enrolment/batches",
        expect.anything(),
      ),
    );
    expect(screen.queryByText("Enrol an agency's file")).toBeNull();
    expect(screen.queryByLabelText("Programme name")).toBeNull();
  });

  it("will not check until there is a programme name and a file", async () => {
    renderUi(<EnrolmentUpload />);
    const check = await screen.findByRole("button", { name: "Check the file" });
    expect((check as HTMLButtonElement).disabled).toBe(true);
    await name("PMKVY-2026");
    expect((check as HTMLButtonElement).disabled).toBe(true);
    await choose();
    expect((check as HTMLButtonElement).disabled).toBe(false);
  });

  it("sends the file and the programme to check, and shows masked rows with the problems first", async () => {
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));

    expect(
      await screen.findByText(/1 new, 1 existing and tagged/),
    ).toBeTruthy();
    const [path, init] = POST.mock.calls[0];
    expect(path).toBe("/ops/enrolment/check");
    expect(init.params.query).toEqual({
      programme: "PMKVY-2026",
      file_name: "agency.csv",
    });
    expect(init.body).toBe("phone\r\n9810000001\r\n");

    const items = screen
      .getAllByRole("listitem")
      .map((li) => li.textContent ?? "");
    const first = items.findIndex((t) => t.includes("Row 3"));
    const second = items.findIndex((t) => t.includes("Row 2"));
    expect(first).toBeGreaterThanOrEqual(0);
    expect(first).toBeLessThan(second);
    expect(screen.getByText(/Anita · \+9198\*\*\*\*\*001/)).toBeTruthy();
  });

  it("will not enrol until the attestation is ticked, then sends it", async () => {
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));
    const enrol = await screen.findByRole("button", { name: "Enrol 2 people" });
    expect((enrol as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByLabelText(/privacy notice was read out/));
    expect((enrol as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(enrol);

    expect(await screen.findByText("Enrolled")).toBeTruthy();
    const apply = POST.mock.calls.find((c) => c[0] === "/ops/enrolment/apply");
    expect(apply?.[1].params.query).toEqual({
      programme: "PMKVY-2026",
      file_name: "agency.csv",
      attest: true,
    });
    // Used once: the review and the button are gone, and the file is forgotten, so it cannot be
    // sent twice by accident.
    expect(screen.queryByRole("button", { name: /^Enrol / })).toBeNull();
    expect(screen.queryByText("agency.csv")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Check the file",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("forgets the review and the attestation when the programme changes", async () => {
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));
    await screen.findByRole("button", { name: "Enrol 2 people" });
    fireEvent.click(screen.getByLabelText(/privacy notice was read out/));

    await name("A-DIFFERENT-ONE");
    expect(screen.queryByRole("button", { name: /^Enrol / })).toBeNull();
    expect(screen.queryByText("What would happen")).toBeNull();
  });

  it("offers the failed rows as a download", async () => {
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Download the rows to fix" }),
    );
    expect(saveCsv).toHaveBeenCalledWith(
      "enrolment-to-fix.csv",
      expect.stringContaining("Ravi"),
    );
  });

  it("says what the server said when it refuses", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "The header row must include: phone." },
      response: { status: 422 },
    });
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));
    expect(
      await screen.findByText("The header row must include: phone."),
    ).toBeTruthy();
  });

  it("sends a signed-out operator to sign in, not to an error", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: {},
      response: { status: 401 },
    });
    renderUi(<EnrolmentUpload />);
    await name("PMKVY-2026");
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Check the file" }));
    expect(await screen.findByText(SIGNED_OUT)).toBeTruthy();
    expect(screen.queryByText("What would happen")).toBeNull();
  });

  it("lists recent enrolments, naming who attested and which notice version", async () => {
    renderUi(<EnrolmentUpload />);
    expect(await screen.findByText("OLDER-PROGRAMME")).toBeTruthy();
    expect(
      screen.getByText(/op\*\*\*\*@example\.com · notice 2026-09/),
    ).toBeTruthy();
    expect(
      screen.getByText("5 new, 1 tagged, 0 left alone, 0 errors"),
    ).toBeTruthy();
  });

  it("suggests the programmes that already exist", async () => {
    renderUi(<EnrolmentUpload />);
    await waitFor(() =>
      expect(
        document.querySelector(
          '#enrol-programmes option[value="OLDER-PROGRAMME"]',
        ),
      ).not.toBeNull(),
    );
  });

  it("refuses a file over the size the server allows without sending it", async () => {
    renderUi(<EnrolmentUpload />);
    const input = (await screen.findByLabelText(
      "Choose the CSV file",
    )) as HTMLInputElement;
    const big = new File(["x"], "big.csv", { type: "text/csv" });
    Object.defineProperty(big, "size", { value: 3 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [big] } });
    expect(await screen.findByText(/larger than 2 MB/)).toBeTruthy();
    expect(POST).not.toHaveBeenCalled();
  });
});
