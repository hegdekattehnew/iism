import type { ReactNode } from "react";

// The locale layout owns <html>; this root layout only passes children through,
// which is what next-intl's [locale] segment requires.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
