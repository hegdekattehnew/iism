import type { VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button-variants";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/** A locale-aware link styled as a button.
 *
 * Separate from `<Button asChild>` because next-intl's `Link` needs the href
 * typed against the route map, which `asChild` would erase.
 */
export function ButtonLink({
  href,
  variant,
  size,
  className,
  children,
}: VariantProps<typeof buttonVariants> & {
  href: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={cn(buttonVariants({ variant, size }), className)}>
      {children}
    </Link>
  );
}
