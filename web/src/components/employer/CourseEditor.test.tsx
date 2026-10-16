import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseEditor } from "@/components/employer/CourseEditor";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(async () => ({ data: [], error: undefined })) },
}));

beforeEach(resetWorld);

/** Sprint 73, UI-26: the form says what a good description is, since the page already lists the standards. */
describe("CourseEditor -- the description field", () => {
  it("says what to write, in the field's own hint", () => {
    renderUi(<CourseEditor course={null} saving={false} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Say who the course is for and what a learner can do afterwards/)).toBeTruthy();
  });
});
