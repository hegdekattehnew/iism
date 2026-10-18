"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { apiErrorFrom } from "@/lib/http";
import { PRIVACY_NOTICE_VERSION } from "@/lib/legal";

/**
 * Consent, from the person's side (Sprint 72, ADR-082): where they stand, withdrawing without
 * deleting the account, and confirming the notice in force (which is both re-consent and restore).
 *
 * The version sent is this build's own `PRIVACY_NOTICE_VERSION`, and a test holds it equal to the
 * API's: a person confirms the text they were shown, and the server refuses any other.
 */
export const CONSENT_KEY = ["me", "consent"] as const;

/** What the server answers (`GET /me/account/consent`). */
export function useConsentState(enabled = true) {
  return useQuery({
    queryKey: CONSENT_KEY,
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/account/consent");
      if (error || !data) throw new Error("consent failed");
      return data;
    },
  });
}

function useRefreshAfter() {
  const qc = useQueryClient();
  // `["me"]` is `/auth/me`, which carries `consent_current` and `consent_withdrawn` the banner reads.
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["me"], exact: true }),
      qc.invalidateQueries({ queryKey: CONSENT_KEY }),
    ]);
}

export function useConfirmConsent() {
  const refresh = useRefreshAfter();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/me/account/consent", {
        body: { consent_version: PRIVACY_NOTICE_VERSION },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });
}

export function useWithdrawConsent() {
  const refresh = useRefreshAfter();
  return useMutation({
    mutationFn: async () => {
      // The status is read before the check: this route declares no error response, so on the
      // failure branch openapi-fetch narrows `response` to `never` (the `useMemberships` note).
      const result = await api.POST("/me/account/consent/withdraw");
      const status = result.response.status;
      const failure: unknown = result.error;
      if (failure || !result.data) throw apiErrorFrom(status, failure);
      return result.data;
    },
    onSuccess: refresh,
  });
}
