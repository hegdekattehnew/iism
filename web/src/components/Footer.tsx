import { getTranslations } from "next-intl/server";

import { LocaleToggle } from "@/components/LocaleToggle";
import { Logo } from "@/components/ui";
import { Link } from "@/i18n/navigation";

const COLUMNS = [
  {
    heading: "product",
    links: [
      { key: "jobs", href: "/jobs", ns: "nav" },
      { key: "courses", href: "/courses", ns: "nav" },
      { key: "skills", href: "/skills", ns: "nav" },
      { key: "howItWorks", href: "/#how-it-works", ns: "nav" },
    ],
  },
  {
    heading: "audiences",
    links: [
      { key: "forEmployers", href: "/employers", ns: "nav" },
      { key: "forProviders", href: "/providers", ns: "nav" },
    ],
  },
  {
    heading: "company",
    links: [
      { key: "about", href: "/about", ns: "footer" },
      { key: "contact", href: "/contact", ns: "footer" },
      { key: "careers", href: "/careers", ns: "footer" },
    ],
  },
  {
    heading: "legal",
    links: [
      { key: "privacy", href: "/privacy", ns: "footer" },
      { key: "terms", href: "/terms", ns: "footer" },
      { key: "grievance", href: "/grievance", ns: "footer" },
    ],
  },
] as const;

export async function Footer() {
  const tf = await getTranslations("footer");
  const tn = await getTranslations("nav");
  const tApp = await getTranslations("app");
  const label = (ns: string, key: string) =>
    ns === "nav" ? tn(key) : tf(key);

  return (
    <footer className="border-t border-border-token bg-surface-muted px-5 py-14">
      <div className="mx-auto w-full max-w-6xl">
        <div className="grid grid-cols-2 gap-8 lg:grid-cols-6">
          <div className="col-span-2">
            <Logo />
            <p className="mt-3 max-w-xs text-sm text-muted">{tApp("tagline")}</p>
            <div className="mt-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {tf("language")}
              </p>
              <LocaleToggle />
            </div>
          </div>

          {COLUMNS.map((col) => (
            <nav key={col.heading} aria-label={tf(col.heading)}>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
                {tf(col.heading)}
              </h3>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => (
                  <li key={l.key}>
                    <Link
                      href={l.href}
                      className="text-sm text-foreground/80 hover:text-brand hover:underline"
                    >
                      {label(l.ns, l.key)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 border-t border-border-token pt-6">
          <p className="text-xs text-muted">{tf("nsqfNote")}</p>
          <p className="mt-2 text-xs text-muted">
            © {new Date().getFullYear()} {tApp("short")}. {tf("rights")}
          </p>
        </div>
      </div>
    </footer>
  );
}
