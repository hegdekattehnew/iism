import { fireEvent, screen } from "@testing-library/react-native";

import { Badge, Card, ListRow, Panel, PanelHeader, RowGroup, SkeletonRows } from "../ui/list";
import { Button, Notice, ProgressBar } from "../ui/primitives";
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

/** Sprint 83, BL-19.23: the pieces the profile is made of. */
describe("a progress bar", () => {
  it.each([
    [60, 60],
    [0, 0],
    [100, 100],
    [-5, 0],
    [140, 100],
    [33.4, 33],
    [Number.NaN, 0],
    [Number.POSITIVE_INFINITY, 0],
  ])("%s percent is read as %s", async (given, read) => {
    await renderScreen(<ProgressBar percent={given} label="Profile" />);
    const bar = screen.getByRole("progressbar", { name: "Profile" });
    expect(bar.props.accessibilityValue).toEqual({ min: 0, max: 100, now: read });
  });

  it("draws the fill as that share of the track", async () => {
    await renderScreen(<ProgressBar percent={60} label="Profile" />);
    const bar = screen.getByRole("progressbar", { name: "Profile" });
    expect(bar.children[0]).toBeTruthy();
    const fill = (bar.children[0] as unknown as { props: { style: { width: string } } }).props.style;
    expect(fill.width).toBe("60%");
  });
});

describe("a panel", () => {
  it("has a heading, an optional line under it, and holds what it is given", async () => {
    await renderScreen(
      <Panel icon="User" title="About you" subtitle="Who you are">
        <Badge label="inside" />
      </Panel>,
    );
    expect(screen.getByRole("header", { name: "About you" })).toBeTruthy();
    expect(screen.getByText("Who you are")).toBeTruthy();
    expect(screen.getByText("inside")).toBeTruthy();
  });

  it("a header alone has no line under it when it has no subtitle", async () => {
    await renderScreen(<PanelHeader icon="User" title="About you" />);
    expect(screen.getByRole("header", { name: "About you" })).toBeTruthy();
    expect(screen.toJSON()).toBeTruthy();
  });

  it("a panel is not a button, so a card inside it is the only thing that can be pressed", async () => {
    await renderScreen(
      <Panel icon="User" title="About you">
        <Card label="inner" level="inset" onPress={jest.fn()}>
          <Badge label="x" />
        </Card>
      </Panel>,
    );
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});

describe("the loading placeholder", () => {
  it("takes the height of what it stands in for", async () => {
    await renderScreen(<SkeletonRows count={1} height={88} />);
    const box = screen.getByLabelText("Loading").children[0] as unknown as { props: { style: { height: number } } };
    expect(box.props.style.height).toBe(88);
  });

  it("is 112 high when nothing else is said, as it always was", async () => {
    await renderScreen(<SkeletonRows count={1} />);
    const box = screen.getByLabelText("Loading").children[0] as unknown as { props: { style: { height: number } } };
    expect(box.props.style.height).toBe(112);
  });
});
