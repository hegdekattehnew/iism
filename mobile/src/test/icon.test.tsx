import { render, screen } from "@testing-library/react-native";

import { Icon } from "../ui/icon";
import { SHAPES, type IconName } from "../ui/icon-shapes";

/**
 * The phone draws the web's icons (Sprint 78, BL-19.7, ADR-087). The shapes are generated, so what
 * is tested here is the part that is the phone's own: every icon renders, and an icon is hidden from
 * a screen reader unless it was given a name.
 */
describe("Icon", () => {
  it("has the thirty-odd icons the web draws, every one with at least one path", () => {
    const names = Object.keys(SHAPES);
    expect(names.length).toBeGreaterThanOrEqual(30);
    for (const name of names) expect(SHAPES[name as IconName].length).toBeGreaterThan(0);
  });

  it("an icon with a title is an image a screen reader can name", async () => {
    await render(<Icon name="Search" title="Search" />);
    expect(screen.getByRole("image", { name: "Search" })).toBeTruthy();
  });

  it("an icon beside its word is hidden from a screen reader", async () => {
    await render(<Icon name="MapPin" />);
    expect(screen.queryByRole("image")).toBeNull();
    // `queryByRole` also ignores anything not marked accessible, so what hides it is asserted by its props.
    const root = screen.toJSON() as { props: Record<string, unknown> };
    expect(root.props.accessibilityRole).toBeUndefined();
    expect(root.props.accessibilityLabel).toBeUndefined();
    expect(root.props.importantForAccessibility).toBe("no-hide-descendants");
  });

  it("an icon with a title is shown to a screen reader, as an image with that name", async () => {
    await render(<Icon name="Bell" title="Updates" />);
    const root = screen.toJSON() as { props: Record<string, unknown> };
    expect(root.props.accessibilityRole).toBe("image");
    expect(root.props.accessibilityLabel).toBe("Updates");
    expect(root.props.importantForAccessibility).toBe("yes");
  });

  it("keeps accessibility props off the Svg, which hands every prop to a DOM element on the web", async () => {
    await render(<Icon name="Bell" title="Updates" />);
    const root = screen.toJSON() as { children: { props: Record<string, unknown> }[] };
    const svg = root.children[0].props;
    for (const prop of ["accessible", "accessibilityRole", "accessibilityLabel", "importantForAccessibility"]) {
      expect(svg[prop]).toBeUndefined();
    }
  });

  it("every icon renders (in one render: a test that renders twice leaves overlapping act scopes)", async () => {
    const names = Object.keys(SHAPES) as IconName[];
    await render(
      <>
        {names.map((name) => (
          <Icon key={name} name={name} title={name} />
        ))}
      </>,
    );
    expect(screen.getAllByRole("image")).toHaveLength(names.length);
    for (const name of names) expect(screen.getByRole("image", { name })).toBeTruthy();
  });
});
