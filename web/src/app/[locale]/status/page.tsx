import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { DevPanel } from "@/components/DevPanel";

/**
 * The Sprint 1 architecture check, on its own route.
 *
 * It used to render at the foot of the homepage, where it announced itself as
 * "Development panel — Sprint 1 verification. Not part of the product surface."
 * to anyone who scrolled. Being visually separated is not the same as being
 * absent, and the landing page is the first thing anyone sees.
 *
 * Not linked from anywhere, and absent from a production build: this is a tool
 * for whoever is running the stack, not a page.
 */
export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  if (process.env.NODE_ENV === "production") notFound();

  return <DevPanel />;
}
