import { fireEvent, screen } from "@testing-library/react-native";

import { Badge, Card, ListRow, RowGroup } from "../ui/list";
import { Button, Notice } from "../ui/primitives";
import { renderScreen } from "./harness";
import { resetWorld } from "./mocks";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

// The pill is hidden from a screen reader on purpose (the row's name says it), so look for it anyway.
const HIDDEN = { includeHiddenElements: true };

beforeEach(() => resetWorld());

/** Sprint 82, BL-19.14: the phone's primitives, each from tokens, each with a name and a floor. */
describe("a button", () => {
  it.each(["primary", "secondary", "ghost", "danger", "soft"] as const)("%s presses and has a name", async (variant) => {
    const onPress = jest.fn();
    await renderScreen(<Button variant={variant} label="Go" onPress={onPress} />);
    await fireEvent.press(screen.getByRole("button", { name: "Go" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("looks different in each variant, so a danger button is not a primary one", async () => {
    const looks: string[] = [];
    for (const variant of ["primary", "secondary", "ghost", "danger", "soft"] as const) {
      const view = await renderScreen(<Button variant={variant} label="Go" onPress={jest.fn()} />);
      const style = JSON.stringify(screen.getByRole("button", { name: "Go" }).props.style);
      looks.push(style);
      await view.unmount();
    }
    expect(new Set(looks).size).toBe(5);
  });

  it("does not fire while busy or disabled", async () => {
    const onPress = jest.fn();
    await renderScreen(<Button label="Go" disabled onPress={onPress} />);
    await fireEvent.press(screen.getByRole("button", { name: "Go" }));
    expect(onPress).not.toHaveBeenCalled();
  });
});

describe("a notice", () => {
  it.each(["info", "success", "warning", "danger"] as const)("says its words in the %s tone", async (tone) => {
    await renderScreen(<Notice tone={tone}>Saved it</Notice>);
    expect(screen.getByText("Saved it")).toBeTruthy();
  });

  it("is announced as an alert only when it is an error", async () => {
    await renderScreen(<Notice tone="danger">Could not save</Notice>);
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("is not an alert when it is good news", async () => {
    await renderScreen(<Notice tone="success">Saved</Notice>);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("a badge and a card", () => {
  it.each(["brand", "muted", "success", "warning", "danger", "info"] as const)("%s badge shows its text", async (tone) => {
    await renderScreen(<Badge tone={tone} label="Label" />);
    expect(screen.getByText("Label")).toBeTruthy();
  });

  it("an inset card is a different surface from a card on the page", async () => {
    await renderScreen(
      <>
        <Card label="a">
          <Badge label="One" />
        </Card>
        <Card level="inset" label="b">
          <Badge label="Two" />
        </Card>
      </>,
    );
    const fill = (label: string) => {
      const style = screen.getByLabelText(label).props.style;
      const flat = typeof style === "function" ? style({ pressed: false }) : style;
      return (Array.isArray(flat) ? Object.assign({}, ...flat.flat(Infinity)) : flat).backgroundColor;
    };
    expect(fill("a")).toBeTruthy();
    expect(fill("b")).toBeTruthy();
    expect(fill("a")).not.toBe(fill("b"));
  });
});

describe("a list row", () => {
  it("is a button named by its title, and presses", async () => {
    const onPress = jest.fn();
    await renderScreen(<ListRow icon="Bell" title="Updates" onPress={onPress} />);
    await fireEvent.press(screen.getByRole("button", { name: "Updates" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("is at least 48 dp tall", async () => {
    await renderScreen(<ListRow icon="Bell" title="Updates" onPress={jest.fn()} />);
    const style = screen.getByRole("button", { name: "Updates" }).props.style;
    const flat = Array.isArray(style) ? Object.assign({}, ...style.flat(Infinity)) : style;
    expect(flat.minHeight).toBeGreaterThanOrEqual(48);
  });

  it("draws a count in a pill, caps it at 99+, and draws nothing for zero", async () => {
    const view = await renderScreen(<ListRow icon="Bell" title="Updates" count={3} onPress={jest.fn()} />);
    expect(screen.getByText("3", HIDDEN)).toBeTruthy();
    await view.unmount();
    const big = await renderScreen(<ListRow icon="Bell" title="Updates" count={250} onPress={jest.fn()} />);
    expect(screen.getByText("99+", HIDDEN)).toBeTruthy();
    await big.unmount();
    await renderScreen(<ListRow icon="Bell" title="Updates" count={0} onPress={jest.fn()} />);
    expect(screen.queryByText("0", HIDDEN)).toBeNull();
  });

  it("takes a longer spoken name when given one, and keeps the title drawn", async () => {
    await renderScreen(<ListRow icon="Bell" title="Updates" accessibilityLabel="Updates: 3 new" onPress={jest.fn()} />);
    expect(screen.getByRole("button", { name: "Updates: 3 new" })).toBeTruthy();
    expect(screen.getByText("Updates")).toBeTruthy();
  });

  it("shows a subtitle under the title", async () => {
    await renderScreen(<ListRow icon="Bell" title="Updates" subtitle="Nothing new" onPress={jest.fn()} />);
    expect(screen.getByText("Nothing new")).toBeTruthy();
  });

  it("a group draws a divider above every row but the first", async () => {
    await renderScreen(
      <RowGroup>
        <ListRow icon="Bell" title="One" onPress={jest.fn()} />
        <ListRow icon="Bell" title="Two" onPress={jest.fn()} />
        <ListRow icon="Bell" title="Three" onPress={jest.fn()} />
      </RowGroup>,
    );
    const top = (name: string) => {
      const style = screen.getByRole("button", { name }).props.style;
      const flat = Array.isArray(style) ? Object.assign({}, ...style.flat(Infinity)) : style;
      return flat.borderTopWidth;
    };
    expect([top("One"), top("Two"), top("Three")]).toEqual([0, 1, 1]);
  });
});
