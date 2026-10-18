"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";
import type { components } from "./api-schema";
import { ApiError, apiErrorFrom } from "./http";

export type EnrolmentReport = components["schemas"]["EnrolmentReportOut"];
export type EnrolmentRow = components["schemas"]["EnrolmentRowOut"];
export type EnrolmentBatch = components["schemas"]["EnrolmentBatchOut"];

// The server's own limits (`enrolment_max_rows`, `max_bulk_body_bytes`, the programme name). A file
// the browser can see is too big is refused here rather than uploaded to be refused there.
export const MAX_FILE_BYTES = 2 * 1024 * 1024;
export const PROGRAMME_MIN = 2;
export const PROGRAMME_MAX = 120;

const BATCHES = ["ops", "enrolment", "batches"] as const;

/** The file is the request body, so the typed client is told not to JSON-encode it. */
const csv = {
  bodySerializer: (body: string) => body,
  headers: { "content-type": "text/csv" },
};

export function useEnrolmentBatches() {
  return useQuery({
    queryKey: BATCHES,
    retry: false,
    queryFn: async () => {
      const result = await api.GET("/ops/enrolment/batches", {});
      const errorBody: unknown = result.error;
      if (errorBody || !result.data)
        throw apiErrorFrom(result.response.status, errorBody);
      return result.data.batches;
    },
  });
}

export function useEnrolmentTemplate() {
  return useMutation({
    mutationFn: async () => {
      // Status read before the check: this route takes no parameters and documents no error body,
      // so on the failure branch openapi-fetch narrows the whole result to `never`.
      const result = await api.GET("/ops/enrolment/template", {
        parseAs: "text",
      });
      const status = result.response.status;
      const data: unknown = result.data;
      if (typeof data !== "string") throw new ApiError(status, null);
      return data;
    },
  });
}

type Input = { body: string; programme: string; fileName: string };

/** Say what the file would do. Writes nothing. */
export function useEnrolmentCheck() {
  return useMutation({
    mutationFn: async ({ body, programme, fileName }: Input) => {
      const { data, error, response } = await api.POST("/ops/enrolment/check", {
        params: { query: { programme, file_name: fileName } },
        body,
        ...csv,
      });
      if (error || !data)
        throw apiErrorFrom(response.status, error);
      return data;
    },
  });
}

/** Enrol the file. The attestation is sent as `attest=true`; the server refuses without it. */
export function useEnrolmentApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ body, programme, fileName }: Input) => {
      const { data, error, response } = await api.POST("/ops/enrolment/apply", {
        params: { query: { programme, file_name: fileName, attest: true } },
        body,
        ...csv,
      });
      if (error || !data)
        throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BATCHES });
      // A new programme name, and new counts for one that exists.
      void qc.invalidateQueries({ queryKey: ["ops", "programmes"] });
      void qc.invalidateQueries({ queryKey: ["ops", "programme"] });
      void qc.invalidateQueries({ queryKey: ["ops", "dashboard"] });
    },
  });
}
