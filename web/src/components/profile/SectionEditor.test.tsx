import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SectionEditor, useSectionDefs } from "@/components/profile/SectionEditor";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: (...a: unknown[]) => PUT(...a),
    DELETE: vi.fn(),
  },
}));

const PHLEBOTOMY = {
  slug: "blood-sample-collection",
  name: "Perform sample collection activities",
  nos_code: "HSS/N0513",
};

const SAVED = {
  id: "c1",
  name: "Phlebotomy Technician Certificate",
  issuing_body: "NSDC",
  skill: PHLEBOTOMY,
};

function Certifications({ entries }: { entries: unknown[] }) {
  const defs = useSectionDefs({ certifications: entries } as never);
  const def = defs.find((d) => d.collection === "certifications")!;
  return <SectionEditor {...def} />;
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  PUT.mockReset();
  GET.mockResolvedValue({ data: [PHLEBOTOMY], error: undefined });
  POST.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
  PUT.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
});

const bodyOf = (mock: ReturnType<typeof vi.fn>) =>
  (mock.mock.calls[0][1] as { body: Record<string, unknown> }).body;

/**
 * The operator's certification queue lists only credentials that name a
 * standard, and no screen let a candidate name one, so the queue could never
 * hold a row. The second half of this is a latent bug the missing field hid:
 * editing a certification sent back the `skill` object it was given and no
 * `skill_slug`, which the server read as "no standard".
 */
describe("a certification's linked standard", () => {
  it("is chosen from the national standards and sent as skill_slug", async () => {
    renderUi(<Certifications entries={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    // The fields are a chunk fetched when a form is first opened (Sprint 79).
    fireEvent.change(await screen.findByLabelText("Certificate"), {
      target: { value: "Phlebotomy Technician Certificate" },
    });

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "phleb" } });
    fireEvent.click(await screen.findByRole("button", { name: "Link" }));
    expect(screen.getByText("Perform sample collection activities")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(bodyOf(POST).skill_slug).toBe("blood-sample-collection");
  });

  it("is shown when a saved certification is edited, and a plain edit leaves it alone", async () => {
    renderUi(<Certifications entries={[SAVED]} />);
    // The list row names it too.
    expect(screen.getByText(/Perform sample collection activities/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(await screen.findByRole("button", { name: "Remove link" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    // Not `skill_slug: null`: that would unlink it. Absent means "leave it".
    expect("skill_slug" in bodyOf(PUT)).toBe(false);
  });

  it("is unlinked only when the person removes it", async () => {
    renderUi(<Certifications entries={[SAVED]} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove link" }));
    expect(screen.getByRole("searchbox")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    expect(bodyOf(PUT).skill_slug).toBeNull();
  });

  it("does not submit the certificate when Enter is pressed in the search box", async () => {
    renderUi(<Certifications entries={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));

    const proceeded = fireEvent.keyDown(await screen.findByRole("searchbox"), { key: "Enter" });
    // `fireEvent` returns false when the handler called preventDefault.
    expect(proceeded).toBe(false);
  });
});

/**
 * `/profile` is within a few kilobytes of the first-load ceiling and four sections of fields are a
 * good deal of code that nobody sees until they press Add (Sprint 79). A source guard, because
 * jsdom cannot measure bytes: the editor reaches the fields only through a dynamic `import()`.
 */
describe("the section forms stay out of the first load", () => {
  const editor = readFileSync(join(__dirname, "SectionEditor.tsx"), "utf8");

  it("SectionEditor imports the forms only as a type, and loads them when a form opens", () => {
    expect(editor).toMatch(/import type \{ SectionForm \} from "@\/components\/profile\/section-forms"/);
    expect(editor).not.toMatch(/^import \{[^}]*\} from "@\/components\/profile\/section-forms"/m);
    expect(editor).toMatch(/import\("@\/components\/profile\/section-forms"\)/);
  });

  it("and nothing else in the profile imports them statically", () => {
    for (const file of ["ProfileEditor.tsx", "OnboardingWizard.tsx", "AboutSection.tsx"]) {
      const path = file === "ProfileEditor.tsx" ? join(__dirname, "..", file) : join(__dirname, file);
      expect(readFileSync(path, "utf8"), file).not.toMatch(/from "@\/components\/profile\/section-forms"/);
    }
  });
});
