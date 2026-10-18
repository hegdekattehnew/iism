// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authHintScript } from "@/lib/auth-hint";
import { ACCESS_TOKEN_KEY } from "@/lib/storage-keys";

const root = document.documentElement;
const run = () => new Function(authHintScript)();
const at = (path: string) => window.history.pushState({}, "", path);

beforeEach(() => {
  localStorage.clear();
  root.removeAttribute("data-auth");
  at("/en/jobs");
});
afterEach(() => vi.restoreAllMocks());

describe("the pre-paint hint that the page needs room for a tab bar", () => {
  it("is set for a browser that holds a sign-in, on a job seeker's page", () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "token");
    run();
    expect(root.getAttribute("data-auth")).toBe("1");
  });

  it("is not set for a browser with no sign-in", () => {
    run();
    expect(root.hasAttribute("data-auth")).toBe(false);
  });

  it.each(["/en/employer/acme", "/hi/employer/acme/team", "/en/admin", "/en/signin", "/ms/signup/seeker", "/en/employers/signin"])(
    "is not set on %s, where there is no bar",
    (path) => {
      localStorage.setItem(ACCESS_TOKEN_KEY, "token");
      at(path);
      run();
      expect(root.hasAttribute("data-auth")).toBe(false);
    },
  );

  it("is set on the public employers page, which is not a workspace", () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "token");
    at("/en/employers");
    run();
    expect(root.getAttribute("data-auth")).toBe("1");
  });

  it("never throws, whatever storage does", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(run).not.toThrow();
  });

  it("is self-contained plain script that names the one key it reads", () => {
    expect(authHintScript).toContain(ACCESS_TOKEN_KEY);
    expect(authHintScript).not.toMatch(/\b(import|export|let|const)\b|=>/);
  });
});
