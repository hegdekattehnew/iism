"use client";

import { useEffect, useState, type ComponentType } from "react";

import { usePathname } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { showsTabBar } from "@/lib/nav";
import { useMemberships } from "@/lib/org";

/**
 * Brings in the job seeker's bottom tab bar when there should be one (Sprint 81, BL-19.13, ADR-090).
 *
 * The bar is a separate chunk (`MobileTabBar`: four icons and a nav) fetched only for a signed-in
 * account that holds a job-seeker profile, on a page that is not an organisation's workspace, the
 * back office or a sign-in page. What stays in every route's first load is this stub, which is small
 * because it reads the same two hooks the header already does.
 *
 * It also keeps the page's room for the bar honest: the head script sets `data-auth` from a guess
 * (a stored sign-in, a path), and this removes it when the account turns out to have no bar to show
 * (an organisation-only account, or a client-side move into a workspace).
 */
export function SeekerTabs() {
  const signedIn = useIsSignedIn();
  const { isJobSeeker, isPending } = useMemberships();
  const pathname = usePathname();
  const [Bar, setBar] = useState<ComponentType | null>(null);

  const place = signedIn && showsTabBar(pathname);
  const wanted = place && isJobSeeker;
  const room = place && (isPending || isJobSeeker);

  useEffect(() => {
    document.documentElement.toggleAttribute("data-auth", room);
    if (wanted && !Bar) void import("@/components/MobileTabBar").then((m) => setBar(() => m.MobileTabBar));
  }, [room, wanted, Bar]);

  return wanted && Bar ? <Bar /> : null;
}
