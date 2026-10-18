import { describe, expect, it } from "vitest";

import { TAB_ITEMS, currentHref, isReducedHeader, showsTabBar } from "@/lib/nav";

describe("currentHref", () => {
  const nav = ["/jobs", "/courses", "/skills", "/#how-it-works"];

  it("is the link that is the page", () => {
    expect(currentHref(nav, "/jobs")).toBe("/jobs");
    expect(currentHref(nav, "/courses")).toBe("/courses");
  });

  it("is the link that is a parent of the page", () => {
    expect(currentHref(nav, "/jobs/ward-attendant-pune")).toBe("/jobs");
  });

  it("is never a link that merely starts with the same letters", () => {
    expect(currentHref(["/job"], "/jobs")).toBeNull();
    expect(currentHref(["/jobs"], "/jobsearch")).toBeNull();
  });

  it("is never a link to a place in a page, or to nowhere", () => {
    expect(currentHref(["/#how-it-works"], "/")).toBeNull();
    expect(currentHref(["", "/jobs"], "/")).toBeNull();
    expect(currentHref(nav, "/about")).toBeNull();
  });

  it("is the deeper link when two nest, so an organisation's team page is the team's", () => {
    const org = ["/employer/acme", "/employer/acme/team"];
    expect(currentHref(org, "/employer/acme")).toBe("/employer/acme");
    expect(currentHref(org, "/employer/acme/jobs/x/applications")).toBe("/employer/acme");
    expect(currentHref(org, "/employer/acme/team")).toBe("/employer/acme/team");
    expect(currentHref(org, "/employer/acme/team/invite")).toBe("/employer/acme/team");
  });
});

describe("isReducedHeader", () => {
  it("is true while signing in or up, in any of its steps", () => {
    for (const p of ["/signin", "/signup", "/signup/seeker", "/signup/employer", "/employers/signin"]) {
      expect(isReducedHeader(p), p).toBe(true);
    }
  });

  it("is false everywhere else, including the page that only sounds like it", () => {
    for (const p of ["/", "/jobs", "/employers", "/signing", "/signin-help", "/profile"]) {
      expect(isReducedHeader(p), p).toBe(false);
    }
  });
});

describe("showsTabBar", () => {
  it("is for a job seeker's pages", () => {
    for (const p of ["/", "/jobs", "/jobs/x", "/courses", "/matches", "/profile", "/applications", "/account"]) {
      expect(showsTabBar(p), p).toBe(true);
    }
  });

  it("is not for an organisation's workspace, the back office or signing in", () => {
    for (const p of ["/employer/acme", "/employer/acme/team", "/admin", "/signin", "/signup/seeker", "/employers/signin"]) {
      expect(showsTabBar(p), p).toBe(false);
    }
  });

  it("the public employers page is not a workspace and keeps the bar", () => {
    expect(showsTabBar("/employers")).toBe(true);
  });
});

describe("the tab bar's four", () => {
  it("are the owner's choice, in the owner's order", () => {
    expect(TAB_ITEMS.map((i) => i.href)).toEqual(["/jobs", "/courses", "/matches", "/profile"]);
  });
});
