import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import { BriefcaseIcon } from "@/components/ui/icons";
import { MetricTile } from "@/components/ui/metric-tile";

import messages from "@/messages/en.json";

const show = (ui: React.ReactElement) =>
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );

/** Sprint 88, BL-19.18: a dashboard figure with a mark; the figure itself is still StatTile's. */
describe("MetricTile", () => {
  it("draws the number and its label, with a mark that a screen reader skips", () => {
    const { container } = show(<MetricTile icon={<BriefcaseIcon />} value={7} label="Posted vacancies" />);
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.getByText("Posted vacancies")).toBeTruthy();
    const mark = container.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(mark.querySelector("svg")).toBeTruthy();
  });

  it("is a dash for a number that has not arrived, never a zero", () => {
    show(<MetricTile icon={<BriefcaseIcon />} value={null} label="Open" />);
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.queryByText("0")).toBeNull();
  });

  it("shows a true zero as 0", () => {
    show(<MetricTile icon={<BriefcaseIcon />} value={0} label="Hired" />);
    expect(screen.getByText("0")).toBeTruthy();
  });

  it("carries the secondary line, and groups Indian-style", () => {
    show(<MetricTile icon={<BriefcaseIcon />} value={12345} label="Seen" secondary="1 rating" />);
    expect(screen.getByText("12,345")).toBeTruthy();
    expect(screen.getByText("1 rating")).toBeTruthy();
  });

  it("sits on the muted surface and takes a class from its caller", () => {
    const { container } = show(<MetricTile icon={<BriefcaseIcon />} value={1} label="x" className="col-span-2" />);
    const tile = container.firstElementChild as HTMLElement;
    expect(tile.className).toContain("bg-surface-muted");
    expect(tile.className).toContain("col-span-2");
  });
});
