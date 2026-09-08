import { redirect } from "next/navigation";

/**
 * Kept as a redirect, not deleted.
 *
 * Sign-in is one door now, taking either a phone or an email: after Sprint 13
 * one identity can hold both credentials, so the credential no longer says who
 * you are. This path is still linked from the employers page, from the
 * workspace's signed-out card, and from whatever anyone has bookmarked.
 */
export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect(`/${locale}/signin`);
}
