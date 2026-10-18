import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateNav } from "@/components/CandidateNav";
import { CandidateStrip } from "@/components/CandidateStrip";
import { Header } from "@/components/Header";
import { MobileTabBar } from "@/components/MobileTabBar";
import { SeekerTabs } from "@/components/SeekerTabs";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

let unread = 0;
vi.mock("@/lib/unread-count", () => ({ useUnreadCount: () => unread }));

beforeEach(() => {
  resetWorld();
  localStorage.clear();
  document.documentElement.removeAttribute("data-auth");
  unread = 0;
});

const nav = (name: string) => screen.getByRole("navigation", { name });

describe("the header marks the page the person is on", () => {
  it("the current link is aria-current, and no other", () => {
    world.pathname = "/courses";
    renderUi(<Header />);
    const main = nav("Main");
    expect(main.querySelector('[aria-current="page"]')?.textContent).toBe("Courses");
    expect(main.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  });

  it("a page inside a section marks the section", () => {
    world.pathname = "/jobs/ward-attendant-pune";
    renderUi(<Header />);
    expect(nav("Main").querySelector('[aria-current="page"]')?.textContent).toBe("Jobs");
  });

  it("a page that is in none of them marks none", () => {
    world.pathname = "/about";
    renderUi(<Header />);
    expect(document.querySelector('[aria-current="page"]')).toBeNull();
  });

  it("in an organisation the team page is the team's, not the vacancies'", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme/team";
    renderUi(<Header />);
    expect(nav("Main").querySelector('[aria-current="page"]')?.textContent).toBe("Team");
  });
});

describe("the reduced header", () => {
  it.each(["/signin", "/signup", "/signup/seeker", "/employers/signin"])("on %s it is the logo and the language", (path) => {
    world.pathname = path;
    renderUi(<Header />);
    expect(screen.getByRole("link", { name: "IISM" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Open menu" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Jobs" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Sign in" })).toBeNull();
  });

  it("everywhere else it is the whole header", () => {
    world.pathname = "/jobs";
    renderUi(<Header />);
    expect(screen.getByRole("link", { name: "Jobs" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open menu" })).toBeTruthy();
  });
});

describe("the mobile menu", () => {
  it("opens, marks the current page, and closes on Escape or a tap outside", () => {
    world.pathname = "/courses";
    renderUi(<Header />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const panel = document.getElementById("mobile-nav")!;
    expect(panel.querySelector('[aria-current="page"]')?.textContent).toBe("Courses");
    expect(panel.className).toContain("overflow-y-auto");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.getElementById("mobile-nav")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(document.getElementById("mobile-nav")).not.toBeNull();
    fireEvent.pointerDown(document.body);
    expect(document.getElementById("mobile-nav")).toBeNull();
  });
});

describe("the candidate's own pages", () => {
  it("are all one tap away, saved jobs and updates among them, with no menu to open", () => {
    world.pathname = "/saved";
    renderUi(<CandidateStrip />);
    const strip = nav("Your pages");
    const links = [...strip.querySelectorAll("a")].map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["My matches", "/matches"],
      ["My applications", "/applications"],
      ["Saved jobs", "/saved"],
      ["Updates", "/notifications"],
      ["My profile", "/profile"],
      ["Courses I asked about", "/interests"],
      ["Where you could move next", "/career-paths"],
      ["Account", "/account"],
    ]);
    expect(strip.querySelector('[aria-current="page"]')?.textContent).toBe("Saved jobs");
  });

  it("says how many updates are unread, drawn in the corner and spoken once in words", () => {
    unread = 3;
    world.pathname = "/matches";
    renderUi(<CandidateStrip />);
    const updates = screen.getByRole("link", { name: /Updates/ });
    expect(updates.querySelector('[aria-hidden="true"]')?.textContent).toBe("3");
    expect(updates.querySelector(".sr-only")?.textContent).toBe("3 unread");
    expect(updates.querySelector('[aria-hidden="true"]')!.className).toContain("absolute"); // out of the flow
  });

  it("has no count to show when there is nothing unread", () => {
    world.signedIn = false;
    world.pathname = "/matches";
    renderUi(<CandidateStrip />);
    expect(screen.getByRole("link", { name: "Updates" }).querySelector("span")).toBeNull();
  });

  it("scrolls sideways rather than wrapping, and every tab is 44 px", () => {
    renderUi(<CandidateStrip />);
    expect(nav("Your pages").className).toContain("overflow-x-auto");
    for (const a of nav("Your pages").querySelectorAll("a")) expect(a.className).toContain("min-h-11");
  });
});

describe("CandidateNav holds the strip's place and fetches the strip", () => {
  it("renders its place at once, whoever is looking, and the strip into it afterwards", async () => {
    world.signedIn = false;
    world.pathname = "/matches";
    const { container } = renderUi(<CandidateNav />);
    const place = container.firstElementChild as HTMLElement;
    expect(place.className).toContain("min-h-12"); // the strip's own height: its arrival moves nothing
    expect(screen.queryByRole("navigation", { name: "Your pages" })).toBeNull();
    await waitFor(() => expect(nav("Your pages")).toBeTruthy());
    expect(place.contains(nav("Your pages"))).toBe(true);
  });

  it("the strip stays out of the first load: the page imports the stub, never the strip", () => {
    const stub = readFileSync(join(__dirname, "CandidateNav.tsx"), "utf8");
    expect(stub).not.toMatch(/^import .*CandidateStrip/m);
    expect(stub).toMatch(/import\("@\/components\/CandidateStrip"\)/);
  });
});

describe("the bottom tab bar", () => {
  it("is Jobs, Courses, Matches and Profile, the current one marked and the bar hidden from a laptop", () => {
    world.pathname = "/matches";
    renderUi(<MobileTabBar />);
    const bar = nav("Main tabs");
    expect(bar.className).toContain("lg:hidden");
    expect(bar.className).toContain("fixed");
    expect([...bar.querySelectorAll("a")].map((a) => a.textContent)).toEqual(["Jobs", "Courses", "Matches", "Profile"]);
    expect(bar.querySelector('[aria-current="page"]')?.textContent).toBe("Matches");
    for (const a of bar.querySelectorAll("a")) expect(a.className).toContain("min-h-16");
  });

  it("marks the tab of a page inside it", () => {
    world.pathname = "/jobs/ward-attendant-pune";
    renderUi(<MobileTabBar />);
    expect(nav("Main tabs").querySelector('[aria-current="page"]')?.textContent).toBe("Jobs");
  });
});

describe("SeekerTabs: who gets the bar", () => {
  const bar = () => screen.queryByRole("navigation", { name: "Main tabs" });

  it("a signed-in job seeker on one of their pages", async () => {
    world.memberships = [personal()];
    world.pathname = "/jobs";
    renderUi(<SeekerTabs />);
    await waitFor(() => expect(bar()).not.toBeNull());
  });

  it("not somebody signed out", async () => {
    world.signedIn = false;
    renderUi(<SeekerTabs />);
    await act(async () => {
      await new Promise((done) => setTimeout(done, 30));
    });
    expect(bar()).toBeNull();
  });

  it("not an account that only holds an organisation, and not inside a workspace", async () => {
    world.memberships = [org("acme")];
    world.pathname = "/jobs";
    const { unmount } = renderUi(<SeekerTabs />);
    await act(async () => {
      await new Promise((done) => setTimeout(done, 30));
    });
    expect(bar()).toBeNull();
    unmount();

    resetWorld();
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<SeekerTabs />);
    await act(async () => {
      await new Promise((done) => setTimeout(done, 30));
    });
    expect(bar()).toBeNull();
  });

  it("not somebody signed out whose account query has not run (a query that is off reads as pending)", async () => {
    world.signedIn = false;
    world.pending = true;
    document.documentElement.setAttribute("data-auth", "1");
    renderUi(<SeekerTabs />);
    await waitFor(() => expect(document.documentElement.hasAttribute("data-auth")).toBe(false));
    expect(bar()).toBeNull();
  });

  it("not while it cannot yet tell what the account holds", async () => {
    world.pending = true;
    renderUi(<SeekerTabs />);
    await act(async () => {
      await new Promise((done) => setTimeout(done, 30));
    });
    expect(bar()).toBeNull();
  });

  it("corrects the page's room for the bar: kept for a seeker, removed when there will be none", async () => {
    document.documentElement.setAttribute("data-auth", "1");
    world.memberships = [personal()];
    world.pathname = "/jobs";
    const { unmount } = renderUi(<SeekerTabs />);
    await waitFor(() => expect(bar()).not.toBeNull());
    expect(document.documentElement.getAttribute("data-auth")).toBe("1");
    unmount();

    resetWorld();
    world.memberships = [org("acme")];
    renderUi(<SeekerTabs />);
    await waitFor(() => expect(document.documentElement.hasAttribute("data-auth")).toBe(false));
  });
});
