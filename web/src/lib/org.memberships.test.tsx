import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { isSignedOut } from "@/lib/http";

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

let access: string | null = null;
let refresh: string | null = null;
vi.mock("@/lib/auth", () => ({
  getAccessToken: () => access,
  getRefreshToken: () => refresh,
}));

import { useMemberships } from "@/lib/org";

/**
 * A signed-out visitor used to ask `/auth/me` on every page and take a 401 (and a red line in the
 * browser console) for it. The question is only worth asking of someone who could answer it.
 */
function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  GET.mockReset();
  access = null;
  refresh = null;
});

describe("useMemberships", () => {
  it("makes no request when nobody is signed in, and still reports signed out", async () => {
    const { result } = renderHook(() => useMemberships(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(GET).not.toHaveBeenCalled();
    // The same answer the request would have given: downstream code branches on it.
    expect(isSignedOut(result.current.error)).toBe(true);
  });

  it("asks when there is an access token", async () => {
    access = "a";
    GET.mockResolvedValue({
      data: { memberships: [] },
      error: undefined,
      response: { status: 200 },
    });
    const { result } = renderHook(() => useMemberships(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(GET).toHaveBeenCalledWith("/auth/me");
  });

  it("asks when only a refresh token is left, so the client can renew the session", async () => {
    refresh = "r";
    GET.mockResolvedValue({
      data: { memberships: [] },
      error: undefined,
      response: { status: 200 },
    });
    const { result } = renderHook(() => useMemberships(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(GET).toHaveBeenCalledTimes(1);
  });
});
