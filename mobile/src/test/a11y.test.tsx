import { fireEvent, render, screen } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { MAX_FONT_SCALE, MIN_TOUCH } from "../theme";
import { Badge, Chip, SearchBox } from "../ui/list";
import { Button, Notice, Text, TextField } from "../ui/primitives";

/**
 * What the screen reader and the thumb are promised (ADR-077). jsdom has no layout, so these assert
 * the **props** that produce the behaviour (a minimum height, a role, a name, a cap on font growth),
 * not pixels; whether it *feels* right on TalkBack or VoiceOver at 200% is a device check
 * (`mobile/ACCESSIBILITY.md`).
 */
const flat = (node: { props: { style?: unknown } }): { minHeight?: number } =>
  (StyleSheet.flatten(node.props.style as object) ?? {}) as { minHeight?: number };

describe("touch targets", () => {
  it("a button is at least 48 dp tall, whatever its label", async () => {
    await render(<Button label="Go" onPress={() => undefined} />);
    expect(flat(screen.getByRole("button", { name: "Go" })).minHeight).toBeGreaterThanOrEqual(MIN_TOUCH);
  });

  it("a filter chip is at least 48 dp tall (it was 40)", async () => {
    await render(<Chip label="Full time" selected={false} onPress={() => undefined} />);
    expect(flat(screen.getByRole("button", { name: "Full time" })).minHeight).toBeGreaterThanOrEqual(MIN_TOUCH);
  });

  it("a text field is at least 48 dp tall", async () => {
    await render(<TextField label="Phone" value="" onChangeText={() => undefined} />);
    expect(flat(screen.getByLabelText("Phone")).minHeight).toBeGreaterThanOrEqual(MIN_TOUCH);
  });

  it("the search box is at least 48 dp tall", async () => {
    await render(<SearchBox value="" onChangeText={() => undefined} placeholder="Search" />);
    expect(flat(screen.getByLabelText("Search")).minHeight).toBeGreaterThanOrEqual(MIN_TOUCH);
  });
});

describe("names, roles and states", () => {
  it("a chip says whether it is selected", async () => {
    await render(<Chip label="Online" selected onPress={() => undefined} />);
    expect(screen.getByRole("button", { name: "Online" }).props.accessibilityState).toMatchObject({ selected: true });
  });

  it("a busy or disabled button says so and does not fire", async () => {
    const press = jest.fn();
    await render(<Button label="Save" busy onPress={press} />);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
    fireEvent.press(button);
    expect(press).not.toHaveBeenCalled();
  });

  it("a button's spoken name may be longer than its label but always contains it", async () => {
    await render(<Button label="Remove" accessibilityLabel="Remove: Hand hygiene" onPress={() => undefined} />);
    expect(screen.getByRole("button", { name: "Remove: Hand hygiene" })).toBeTruthy();
  });

  it("a title is a heading and a danger notice is an alert", async () => {
    await render(
      <>
        <Text variant="title">Matches</Text>
        <Notice tone="danger">Could not save</Notice>
      </>,
    );
    expect(screen.getByRole("header", { name: "Matches" })).toBeTruthy();
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});

describe("large system fonts", () => {
  it("every piece of text grows with the person's setting, up to the cap and no further", async () => {
    await render(
      <>
        <Text>Body</Text>
        <Button label="Press" onPress={() => undefined} />
        <Chip label="Chip" selected={false} onPress={() => undefined} />
        <Badge label="Badge" />
        <Notice>Note</Notice>
        <TextField label="Field" value="" onChangeText={() => undefined} />
      </>,
    );
    for (const name of ["Body", "Press", "Chip", "Badge", "Note", "Field"]) {
      const node = screen.getByText(name);
      expect(node.props.allowFontScaling).not.toBe(false);
      expect(node.props.maxFontSizeMultiplier).toBe(MAX_FONT_SCALE);
    }
    expect(screen.getByLabelText("Field").props.maxFontSizeMultiplier).toBe(MAX_FONT_SCALE);
  });

  it("the cap is a doubling, the largest step either platform offers", async () => {
    expect(MAX_FONT_SCALE).toBe(2);
  });
});
