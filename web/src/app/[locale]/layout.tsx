import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { QueryProvider } from "@/components/QueryProvider";
import { ServiceWorkerRegistrar } from "@/components/ServiceWorkerRegistrar";
import { routing } from "@/i18n/routing";
import "../globals.css";

/** The address bar and the splash screen, matched to the manifest's colour.
 *  A mismatch here is what makes an installed app look like a web page. */
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1220" },
  ],
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app" });
  return {
    title: t("short"),
    description: t("tagline"),
    manifest: "/manifest.webmanifest",
    // iOS ignores SVG icons entirely, so the PNG is not a nicety -- without it
    // an added-to-home-screen icon is a blank page thumbnail.
    icons: {
      icon: [
        { url: "/icon.svg", type: "image/svg+xml" },
        { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      ],
      apple: "/apple-touch-icon.png",
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const tn = await getTranslations({ locale, namespace: "nav" });

  return (
    <html lang={locale}>
      <body className="flex min-h-screen flex-col antialiased">
        {/* First focusable thing on every page: a keyboard or switch user
            otherwise tabs through the whole header on every navigation. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:shadow-lg"
        >
          {tn("skipToContent")}
        </a>
        <NextIntlClientProvider>
          <QueryProvider>
            <Header />
            {/* tabIndex so the skip link moves focus here, not just scroll. */}
            <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
              {children}
            </main>
            <Footer />
            <ServiceWorkerRegistrar />
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
