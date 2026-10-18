"use client";

import { useEffect, useState, type ComponentType } from "react";

/**
 * A job seeker's own pages, in a row at the top of each of them (Sprint 81, BL-19.13, ADR-090):
 * matches, applications, saved jobs, updates, profile, the courses asked about, career paths and the
 * account. Until now four of these were reachable only through the account menu, and **saved jobs
 * through nothing at all**.
 *
 * The strip is `CandidateStrip`, **fetched after the page has painted**: it is on eight routes, one
 * of which (`/profile`) is within a few kilobytes of the first-load ceiling, and eight links with
 * their messages are not first-paint content. **What is rendered at once is its place**, a row of
 * the strip's own height, so the strip arriving moves nothing (ADR-065). It is rendered whether or
 * not anyone is signed in, for the same reason: a visitor on one of these pages is shown its own
 * sign-in prompt, and a strip that waited for the account would push the page down.
 */
export function CandidateNav() {
  const [Strip, setStrip] = useState<ComponentType | null>(null);
  useEffect(() => {
    let live = true;
    void import("@/components/CandidateStrip").then((m) => live && setStrip(() => m.CandidateStrip));
    return () => {
      live = false;
    };
  }, []);

  return <div className="mb-6 min-h-12">{Strip ? <Strip /> : null}</div>;
}
