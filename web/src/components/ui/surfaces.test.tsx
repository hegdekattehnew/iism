// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Alert } from "./alert";
import { Badge } from "./badge";
import { Button } from "./button";
import { Card, CardBody } from "./card";
import { EmptyState } from "./empty-state";
import { BriefcaseIcon } from "./icons";
import { Spinner } from "./spinner";

/**
 * The surfaces and actions rebuilt on the tokens (Sprint 80, BL-19.11 and BL-19.12, ADR-089). What a
 * browser cannot say about them cheaply: which classes carry which level, what is announced, and what
 * a screen reader is not asked to hear twice.
 */
describe("Card levels", () => {
  const classOf = (level?: "default" | "raised" | "inset" | "interactive") => {
    const { container } = render(<Card level={level}>x</Card>);
    return container.firstElementChild!.className;
  };

  it("the default is what a card always was, with the soft shadow", () => {
    const c = classOf();
    expect(c).toContain("bg-surface");
    expect(c).toContain("border-border-token");
    expect(c).toContain("shadow-card");
    expect(c).toContain("rounded-xl");
  });

  it("raised is the floating surface; inset has no shadow; interactive lifts on hover", () => {
    expect(classOf("raised")).toContain("shadow-raised");
    expect(classOf("raised")).toContain("bg-surface-raised");
    expect(classOf("inset")).not.toContain("shadow");
    expect(classOf("inset")).toContain("bg-surface-muted");
    expect(classOf("interactive")).toContain("hover:shadow-raised");
    expect(classOf("interactive")).toContain("hover:border-brand");
  });

  it("a caller's class still wins over the level's", () => {
    const { container } = render(<Card className="rounded-lg">x</Card>);
    expect(container.firstElementChild!.className).toContain("rounded-lg");
    expect(container.firstElementChild!.className).not.toContain("rounded-xl");
  });

  it("CardBody is still the padding", () => {
    const { container } = render(<CardBody>x</CardBody>);
    expect(container.firstElementChild!.className).toContain("p-5");
  });
});

describe("Badge", () => {
  it("is the 12 px size by default and a larger one on request", () => {
    const { container } = render(
      <>
        <Badge>a</Badge>
        <Badge size="md">b</Badge>
      </>,
    );
    const [small, medium] = [...container.children].map((e) => e.className);
    expect(small).toContain("text-2xs");
    expect(medium).toContain("text-xs");
    expect(medium).not.toContain("text-2xs");
  });

  it("has an info tone beside the others", () => {
    const { container } = render(<Badge tone="info">n</Badge>);
    expect(container.firstElementChild!.className).toContain("bg-info-surface");
  });
});

describe("Button", () => {
  it("has a soft variant and a pressed state on the primary", () => {
    render(
      <>
        <Button variant="soft">Soft</Button>
        <Button>Primary</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Soft" }).className).toContain("bg-accent-tint");
    expect(screen.getByRole("button", { name: "Primary" }).className).toContain("active:brightness-95");
  });

  it("loading disables it, says it is busy and draws a ring that is not announced", () => {
    render(<Button loading>Saving</Button>);
    const button = screen.getByRole("button", { name: "Saving" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.querySelector("[aria-hidden]")).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("is not busy and not disabled otherwise, and keeps its own disabled", () => {
    render(
      <>
        <Button>Ready</Button>
        <Button disabled>Off</Button>
      </>,
    );
    expect((screen.getByRole("button", { name: "Ready" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByRole("button", { name: "Ready" }).getAttribute("aria-busy")).toBeNull();
    expect((screen.getByRole("button", { name: "Off" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("as a child it renders the child and passes disabled through", () => {
    render(
      <Button asChild disabled>
        <span>Go</span>
      </Button>,
    );
    const child = screen.getByText("Go");
    expect(child.tagName).toBe("SPAN");
    expect(child.getAttribute("disabled")).not.toBeNull();
  });
});

describe("Alert", () => {
  it("draws a shape for its tone, in the margin, so the children's layout is untouched", () => {
    const { container } = render(
      <Alert tone="warning" className="space-y-2">
        <p>One</p>
        <p>Two</p>
      </Alert>,
    );
    const alert = screen.getByRole("alert");
    expect(alert.querySelector("svg")).toBeTruthy();
    expect(alert.className).toContain("relative");
    expect(alert.className).toContain("space-y-2");
    expect(container.querySelectorAll("p")).toHaveLength(2);
    expect(alert.textContent).toBe("OneTwo");
  });

  it("each tone has its own icon, and the icon can be left off", () => {
    const shapes = (tone: "danger" | "warning" | "success" | "info") => {
      const { container, unmount } = render(<Alert tone={tone}>x</Alert>);
      const d = [...container.querySelectorAll("path")].map((p) => p.getAttribute("d")).join("|");
      unmount();
      return d;
    };
    const all = (["danger", "warning", "success", "info"] as const).map(shapes);
    expect(new Set(all).size).toBe(4);
    const { container } = render(<Alert icon={false}>x</Alert>);
    expect(container.querySelector("svg")).toBeNull();
  });

  it("is still an alert by default and a status when asked", () => {
    render(
      <>
        <Alert>a</Alert>
        <Alert tone="success" role="status">
          b
        </Alert>
      </>,
    );
    expect(screen.getByRole("alert").textContent).toBe("a");
    expect(screen.getByRole("status").textContent).toBe("b");
  });
});

describe("Spinner", () => {
  it("with a label is a status a screen reader can name", () => {
    render(<Spinner label="Loading" />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeTruthy();
  });

  it("without one is decoration", () => {
    const { container } = render(<Spinner />);
    expect(container.firstElementChild!.getAttribute("aria-hidden")).toBe("true");
    expect(container.firstElementChild!.getAttribute("role")).toBeNull();
  });

  it("only a placeholder hides the footer", () => {
    const { container } = render(
      <>
        <Spinner label="a" />
        <Spinner label="b" placeholder />
      </>,
    );
    const [plain, standing] = [...container.children];
    expect(plain.hasAttribute("data-loading")).toBe(false);
    expect(standing.hasAttribute("data-loading")).toBe(true);
  });
});

describe("EmptyState", () => {
  it("says what is missing under an icon, with why and an action when given", () => {
    const { container } = render(
      <EmptyState title="Nothing here yet" action={<button>Browse</button>}>
        It will appear here.
      </EmptyState>,
    );
    expect(screen.getByText("Nothing here yet")).toBeTruthy();
    expect(screen.getByText("It will appear here.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Browse" })).toBeTruthy();
    expect(container.querySelector("svg")).toBeTruthy();
    expect(screen.queryByRole("heading")).toBeNull(); // it sits under the page's own heading
  });

  it("takes any icon from the set, and art in its place when art arrives", () => {
    const { container, rerender } = render(<EmptyState title="t" icon={BriefcaseIcon} />);
    const icon = container.querySelector("svg")!.innerHTML;
    rerender(<EmptyState title="t" illustration={<span data-testid="art">art</span>} />);
    expect(container.querySelector("svg")).toBeNull();
    expect(screen.getByTestId("art").textContent).toBe("art");
    expect(icon).toContain("path");
  });

  it("hides its picture from assistive technology: the sentence says it all", () => {
    const { container } = render(<EmptyState title="t" illustration={<span>art</span>} />);
    // The disc itself, not just an icon inside it: art that is not an icon must be hidden too.
    expect(container.querySelector("div[aria-hidden]")).toBeTruthy();
  });

  it("omits the body and the action when there are none", () => {
    const { container } = render(<EmptyState title="t" />);
    expect(container.querySelectorAll("p")).toHaveLength(1);
  });
});

describe("the gallery is not in a production build", () => {
  const root = join(__dirname, "..", "..", "..");
  const page = readFileSync(join(root, "src/app/[locale]/gallery/page.tsx"), "utf8");
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as { scripts: Record<string, string> };

  it("the page 404s unless it is development or the browser-test build", () => {
    expect(page).toMatch(/NODE_ENV !== "production" \|\| process\.env\.NEXT_PUBLIC_UI_GALLERY === "1"/);
    expect(page).toMatch(/if \(!GALLERY_ENABLED\) notFound\(\)/);
  });

  it("only the browser-test build switches it on", () => {
    expect(pkg.scripts["build:e2e"]).toContain("NEXT_PUBLIC_UI_GALLERY=1");
    for (const [name, command] of Object.entries(pkg.scripts)) {
      if (name !== "build:e2e") expect(command, name).not.toContain("NEXT_PUBLIC_UI_GALLERY");
    }
  });
});

describe("the barrel stays off the icon factory", () => {
  const barrel = readFileSync(join(__dirname, "index.ts"), "utf8");

  it("does not re-export what draws icons or is heavy: a barrel is on every route that wants a Button", () => {
    // Measured in Sprint 80: naming EmptyState and Spinner here put about 4 KB on /profile.
    for (const name of ["EmptyState", "Spinner", "Dialog"]) {
      expect(barrel, name).not.toMatch(new RegExp(`export \\{[^}]*\\b${name}\\b[^}]*\\} from`));
    }
  });

  it("and the barrel check can fail", () => {
    expect(/export \{[^}]*\bEmptyState\b[^}]*\} from/.test('export { EmptyState } from "x";')).toBe(true);
  });
});

describe("the page-level empty lists say so with an EmptyState", () => {
  const root = join(__dirname, "..");
  const FILES = [
    "JobBrowser.tsx",
    "CourseBrowser.tsx",
    "SkillBrowser.tsx",
    "NotificationsPage.tsx",
    "InterestList.tsx",
    "ApplicationList.tsx",
    "employer/ProviderInbox.tsx",
    "employer/EmployerInbox.tsx",
    "ops/ReportQueue.tsx",
    "ops/GrievanceQueue.tsx",
  ];

  it("each imports the component and no longer renders a bare muted paragraph for nothing", () => {
    expect(FILES.length).toBeGreaterThan(5);
    for (const file of FILES) {
      const source = readFileSync(join(root, file), "utf8");
      expect(source, file).toContain("@/components/ui/empty-state");
      expect(source, file).toMatch(/<EmptyState\b/);
      expect(source, file).not.toMatch(/<p className="mt-[68] (text-sm )?text-muted">\{t\("(noResults|empty|emptyOpen)"\)\}<\/p>/);
    }
  });
});
