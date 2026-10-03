import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobEditor } from "@/components/employer/JobEditor";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(async () => ({ data: [], error: undefined })) },
}));

beforeEach(resetWorld);

const editor = () => (
  <JobEditor job={null} saving={false} onSave={vi.fn()} onCancel={vi.fn()} />
);

const closingDate = () => screen.getByLabelText(/Closing date/) as HTMLInputElement;
const district = () => screen.getByLabelText(/District/) as HTMLInputElement;
const typeSelect = () => screen.getByLabelText(/Employment type/) as HTMLSelectElement;

/**
 * A gig is a vacancy with an end and a place. The server refuses one with no
 * closing date or no resolvable district, and the form used to say neither:
 * the date was labelled "optional" and nothing was required, so an employer
 * filled the whole form in and was told afterwards.
 */
describe("JobEditor -- a gig needs an end and a place", () => {
  it("asks for neither on an ordinary vacancy", () => {
    renderUi(editor());

    expect(closingDate().required).toBe(false);
    expect(district().required).toBe(false);
    expect(screen.getByText(/Optional\. Applications stop/)).toBeTruthy();
  });

  it("requires both, and says so, once the type is a gig", () => {
    renderUi(editor());
    fireEvent.change(typeSelect(), { target: { value: "gig" } });

    expect(closingDate().required).toBe(true);
    expect(district().required).toBe(true);
    expect(screen.getByText(/Required for a gig\. Applications stop/)).toBeTruthy();
    // The "optional" wording would now be false.
    expect(screen.queryByText(/Optional\. Applications stop/)).toBeNull();
  });

  it("stops requiring them when the type is changed back", () => {
    renderUi(editor());
    fireEvent.change(typeSelect(), { target: { value: "gig" } });
    fireEvent.change(typeSelect(), { target: { value: "full_time" } });

    expect(closingDate().required).toBe(false);
    expect(district().required).toBe(false);
  });
});
